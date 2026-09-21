"""Prepare only A CPU oracles after INPUT_FROZEN; never read sealed B-final."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from experiments.gate0.prepare_history import digest
from reference.exact_runs import Record, brute_force
from prepare_inputs import event, save, pick_database, pick_queries


def run(command, out):
    start = time.perf_counter()
    p = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    event(out, 'CPU_COMMAND', argv=command, returncode=p.returncode, wall_s=time.perf_counter()-start,
          stdout=p.stdout, stderr=p.stderr)
    p.check_returncode()


def read_tuples(path):
    data, result, offset = path.read_bytes(), [], 0
    while offset < len(data):
        qid, count = struct.unpack_from('<QQ', data, offset)
        offset += 16
        rows = [struct.unpack_from('<QII', data, offset+16*i) for i in range(count)]
        offset += count * 16
        result.append((qid, rows))
    assert offset == len(data)
    return result


def fixture_checks(binary, out):
    # Independent fraction-based Python oracle from the pinned repository.
    rng = np.random.default_rng(20260921)
    for D in (256, 2048):
        dest = out / ('fixture_' + str(D))
        db, qd = dest/'db', dest/'q'
        db.mkdir(parents=True); qd.mkdir()
        words = D//64
        fp = rng.integers(0, 2**64-1, size=(129, words), dtype='<u8')
        fp[0] = 0; fp[1] = 2**64-1; fp[2] = fp[1]; fp[3] = 0; fp[3,0] = 127
        fp[4] = 0; fp[4,0] = 63 | (1<<10)
        ids = np.arange(129, dtype='<u8')
        q = fp[[1,3,64,128]].copy(); q[1]=0; q[1,0]=1023
        qids = np.arange(1000,1004, dtype='<u8')
        ids.tofile(db/'ids.u64'); fp.tofile(db/'fp.u64'); qids.tofile(qd/'ids.u64'); q.tofile(qd/'fp.u64')
        records = [Record(int(i), int.from_bytes(x.tobytes(),'little')) for i,x in zip(ids,fp)]
        for m,n in ((1,2),(7,10),(4,5),(1,1),(2147483647,2147483647)):
            output=dest/f'{m}_{n}.bin'
            run([str(binary),str(db),str(qd),str(D),str(m),str(n),str(output),'129'],out)
            got=read_tuples(output)
            for (qid,tuples),expected_id,x in zip(got,qids,q):
                expected=brute_force(records,int.from_bytes(x.tobytes(),'little'),Fraction(m,n))
                assert qid==expected_id and tuples==[(h.source_id,h.intersection,h.union) for h in expected]
        # Reject empty query and invalid parameters without substituting results.
        q[0]=0; q.tofile(qd/'fp.u64')
        p=subprocess.run([str(binary),str(db),str(qd),str(D),'7','10',str(dest/'rejected_zero.bin'),'129'],capture_output=True,text=True)
        assert p.returncode and 'zero query' in p.stderr
    event(out,'NATIVE_ORACLE_FIXTURES_PASS', scope='CPU oracle only; not native content-filter capacities')


def sampling_checks(out):
    rng=np.random.default_rng(1);ids=np.arange(3000,dtype='<u8')
    fp=rng.integers(1,2**63,size=(3000,4),dtype='<u8');fp[1500:1600]=fp[1800:1900];fp[2950:]=0
    import hashlib
    def key(i,seed):return(hashlib.sha256(f'{seed}|fixture|{i}'.encode()).digest(),int(i))
    assert list(pick_database(ids,'fixture',out))==sorted(range(3000),key=lambda i:key(i,20260921))
    reps={};old_ids={2,3};old_bits={fp[42].tobytes()}
    for i in range(3000):
        bits=fp[i].tobytes()
        if i<20 or i in old_ids or bits in old_bits or not any(bits):continue
        if bits not in reps or key(i,20260922)<key(reps[bits],20260922):reps[bits]=i
    expected=sorted(reps.values(),key=lambda i:key(i,20260922))[:896]
    assert list(pick_queries(ids,fp,ids[:20],old_ids,old_bits,'fixture',out))==expected
    event(out,'SAMPLING_STREAMING_VS_FULL_SORT_PASS')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);out=a.output.resolve();data=a.input.resolve()
    resource.setrlimit(resource.RLIMIT_AS,(8<<30,8<<30))
    try:
        manifest=json.loads((data/'INPUT_FROZEN.json').read_text())
        save(out/'ORACLE_FROZEN.json',{'input_manifest_sha256':digest(data/'INPUT_FROZEN.json'),
             'oracle_source_sha256':digest(HERE/'oracle.cpp'),'runner_source_sha256':digest(Path(__file__)),
             'role':'independent_CPU_raw_AND_OR_popcount_complete_tuple_oracle','gpu':'NOT_USED',
             'pid':os.getpid(),'threads':1,'screen_counts_not_used_for_selection':True})
        binary=out/'oracle'
        run(['g++','-std=c++17','-O3','-march=native','-Wall','-Wextra','-Werror',str(HERE/'oracle.cpp'),'-o',str(binary)],out)
        sampling_checks(out);fixture_checks(binary,out)
        artifacts=[]
        for lane in manifest['lanes']:
            D=lane['D']; name=lane['name'];db=data/lane['artifacts']['database_100k']['relative_path']
            for split in ('dev','a_screen'):
                qd=data/lane['artifacts'][split]['relative_path']
                for directory,item in ((db,lane['artifacts']['database_100k']),(qd,lane['artifacts'][split])):
                    assert digest(directory/'ids.u64')==item['ids_sha256']
                    assert digest(directory/'fp.u64')==item['fp_sha256']
                if split == 'dev':
                    small = out / (name + '_real_crosscheck')
                    sdb, sq = small/'db', small/'q'
                    sdb.mkdir(parents=True); sq.mkdir()
                    ids = np.fromfile(db/'ids.u64',dtype='<u8',count=256)
                    fp = np.fromfile(db/'fp.u64',dtype='<u8',count=256*(D//64)).reshape(256,-1)
                    qids = np.fromfile(qd/'ids.u64',dtype='<u8',count=8)
                    qfp = np.fromfile(qd/'fp.u64',dtype='<u8',count=8*(D//64)).reshape(8,-1)
                    ids.tofile(sdb/'ids.u64'); fp.tofile(sdb/'fp.u64')
                    qids.tofile(sq/'ids.u64'); qfp.tofile(sq/'fp.u64')
                    records = [Record(int(i),int.from_bytes(x.tobytes(),'little')) for i,x in zip(ids,fp)]
                    for m,n in ((7,10),(4,5)):
                        target=small/f'{m}_{n}.bin'
                        run([str(binary),str(sdb),str(sq),str(D),str(m),str(n),str(target),'256'],out)
                        got=read_tuples(target)
                        for (qid,tuples),expected_id,x in zip(got,qids,qfp):
                            expected=brute_force(records,int.from_bytes(x.tobytes(),'little'),Fraction(m,n))
                            assert qid==expected_id and tuples==[(h.source_id,h.intersection,h.union) for h in expected]
                    event(out,'REAL_DATA_SECOND_ORACLE_PASS',lane=name,queries=8,rows=256)
                for m,n in ((7,10),(4,5)):
                    dest=out/f'{name}_{split}_{m}_{n}.bin'
                    run([str(binary),str(db),str(qd),str(D),str(m),str(n),str(dest),'100000'],out)
                    # Full artifact hash; no screen result-cardinality selection.
                    artifacts.append({'lane':name,'split':split,'m':m,'n':n,'file':dest.name,'bytes':dest.stat().st_size,'sha256':digest(dest)})
        save(out/'ORACLE_COMPLETE.json',{'status':'CPU_ORACLES_READY_NOT_A_GO','artifacts':artifacts,
              'binary_sha256':digest(binary),'max_rss_self_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              'max_rss_children_bytes':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024})
        event(out,'A_ORACLES_COMPLETE',files=len(artifacts),gpu='NOT_USED')
    except BaseException as exc:
        event(out,'FAILED_PRESERVED',error=repr(exc));raise


if __name__=='__main__':main()
