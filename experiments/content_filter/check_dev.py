"""CPU real-dev correctness grid only; no parameter selection or A-screen run.

The shared verifier is full raw AND/popcount for this semantic checkpoint.
Access accounting and dev selection remain separate, unfinished gates.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

import numpy as np
from prepare_inputs import event, save
from run_oracle import read_tuples
from reference_semantics import Index, CONFIGS
from experiments.gate0.prepare_history import digest


def ids_hash(ids):
    h=hashlib.sha256()
    for rid in sorted(ids):h.update(struct.pack('<Q',rid))
    return h.hexdigest()


def load_rows(path, D):
    ids=np.fromfile(path/'ids.u64',dtype='<u8')
    fp=np.fromfile(path/'fp.u64',dtype='<u8').reshape(len(ids),D//64)
    return [(int(i),int.from_bytes(x.tobytes(),'little')) for i,x in zip(ids,fp)]


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--oracle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);out=a.output
    resource.setrlimit(resource.RLIMIT_AS,(8<<30,8<<30))
    resource.setrlimit(resource.RLIMIT_CPU,(24*60*60,24*60*60))
    try:
        frozen=json.loads((a.input/'INPUT_FROZEN.json').read_text())
        oracle=json.loads((a.oracle/'ORACLE_COMPLETE.json').read_text())
        oracle_map={(x['lane'],x['split'],x['m'],x['n']):x for x in oracle['artifacts']}
        save(out/'DEV_CHECK_FROZEN.json',{'input_sha256':digest(a.input/'INPUT_FROZEN.json'),
             'oracle_manifest_sha256':digest(a.oracle/'ORACLE_COMPLETE.json'),
             'implementation_sha256':digest(Path(__file__).with_name('reference_semantics.py')),
             'runner_sha256':digest(Path(__file__)), 'split':'dev_only', 'gpu':'NOT_USED',
             'purpose':'full real-data reference semantics, not access/timing selection',
             'V':'R0 full raw verifier', 'configs':CONFIGS, 'cpu_limit_s':24*60*60})
        fields=['lane','query_id','m','n','method','config','C','H','S','false_negative_count',
                'false_positive_count','tuple_mismatch_count','duplicate_id_count','survivor_sha256',
                'cpu_diagnostic_s','logical_total_bytes','sector_proxy_bytes']
        with (out/'reference_dev_correctness.csv').open('x') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();count=0
            for lane in frozen['lanes']:
                name,D=lane['name'],lane['D']; art=lane['artifacts']
                for kind in ('database_100k','dev'):
                    directory=a.input/art[kind]['relative_path']
                    assert digest(directory/'ids.u64')==art[kind]['ids_sha256']
                    assert digest(directory/'fp.u64')==art[kind]['fp_sha256']
                rows=load_rows(a.input/art['database_100k']['relative_path'],D)
                queries=load_rows(a.input/art['dev']['relative_path'],D)
                event(out,'BUILD_REFERENCE_INDEX',lane=name,N=len(rows),D=D)
                index=Index(rows,D)
                expected={}
                for m,n in ((7,10),(4,5)):
                    item=oracle_map[name,'dev',m,n];source=a.oracle/item['file']
                    assert digest(source)==item['sha256']
                    expected[m,n]=dict(read_tuples(source))
                for qi,(qid,q) in enumerate(queries):
                    for m,n in ((7,10),(4,5)):
                        truth=expected[m,n][qid];truth_ids={x[0] for x in truth};seen={}
                        pop=q.bit_count();lo=(m*pop+n-1)//n;hi=min(D,n*pop//m)
                        C=sum(len(bucket) for b,bucket in index.buckets.items() if lo<=b<=hi)
                        for method,config in CONFIGS:
                            start=time.perf_counter();got,survivors=index.search(q,m,n,method,config)
                            seconds=time.perf_counter()-start
                            got_ids={x[0] for x in got}; fn=len(truth_ids-got_ids);fp=len(got_ids-truth_ids)
                            exact=dict((x[0],x[1:]) for x in truth)
                            mismatch=sum(1 for x in got if x[0] in exact and x[1:]!=exact[x[0]])
                            duplicate=len(got)-len(got_ids)
                            writer.writerow(dict(lane=name,query_id=qid,m=m,n=n,method=method,config=config,
                                C=C,H=len(truth),S=len(survivors) if method in ('R2','B','P') else 'NA',
                                false_negative_count=fn,false_positive_count=fp,tuple_mismatch_count=mismatch,
                                duplicate_id_count=duplicate,survivor_sha256=ids_hash(survivors) if method in ('B','P') else 'NA',
                                cpu_diagnostic_s=seconds,logical_total_bytes='NA',sector_proxy_bytes='NA'))
                            stream.flush();count+=1
                            if fn or fp or mismatch or duplicate or got!=truth:
                                event(out,'CORRECTNESS_FAIL',lane=name,query_id=qid,m=m,n=n,method=method,config=config)
                                raise AssertionError('complete tuple mismatch; row retained')
                            if method in ('B','P'):seen[method,config]=survivors
                        assert seen['B',1]==seen['P',1] and seen['B',8]==seen['P',8]
                    if qi%8==0:event(out,'REFERENCE_DEV_PROGRESS',lane=name,queries=qi+1,rows=count)
                del index,rows,queries
            save(out/'REFERENCE_DEV_COMPLETE.json',{'status':'REFERENCE_DEV_PASS_NOT_A_GO',
                'method_query_threshold_rows':count,'csv_sha256':digest(out/'reference_dev_correctness.csv'),
                'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                'missing_gates':['complete_access_accounting','dev_selection','A-screen','native_GPU']})
            event(out,'REFERENCE_DEV_COMPLETE',rows=count)
    except BaseException as exc:
        event(out,'FAILED_PRESERVED',error=repr(exc));raise


if __name__=='__main__':main()
