"""Accept only the full frozen campaign; retain every attempt/case and raw hash."""
import argparse
import csv
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.gate2.metrics import digest, summarize, passes, choose, rows, interval_for


def verify_summary(computed, recorded):
    if computed.keys() != recorded.keys():
        raise ValueError("summary fields differ")
    for key in computed:
        # Python 3.12 changed built-in float sum; the frozen runner used it for
        # this mean only. Keep the recorded value, with a narrow numerical check.
        equal = (math.isclose(computed[key], recorded[key], rel_tol=1e-12, abs_tol=1e-12)
                 if key == "mean_service_ms" else computed[key] == recorded[key])
        if not equal:
            raise ValueError("raw reanalysis differs from campaign summary: "+key)


def audit_timeline(raw, name, case):
    requests = rows(raw/(name+".requests.csv"))
    arrivals = rows(raw/(name+".arrivals.csv"))
    life = rows(raw/(name+".coverage.csv"))
    allocations = rows(raw/(name+".arena.csv"))
    workspace = int(next(e for e in allocations if e["event"] == "alloc")["bytes"])
    for m in rows(raw/(name+".maintenance.csv")):
        classified = sum(int(m[k]) for k in ("shared_bytes", "current_only_bytes", "reader_only_at_publish_bytes", "other_held_at_publish_bytes"))
        if classified+workspace != int(m["live_at_publish_bytes"]):
            raise ValueError("unique-owner byte balance does not close")
        if int(m["retired_only_bytes"]) and float(m["exclusive_actual_reclaim_ms"]) < float(m["last_reader_device_done_ms"]):
            raise ValueError("exclusive GPU allocation reclaimed before old reader completed")
    end = case["start_ms"]+case["window_ms"]
    seen = [0]*7
    for request, arrival in zip(requests, arrivals):
        if float(arrival["returned_ms"]) <= end:
            seen[int(request["epoch"])] += 1
    if seen != case["seen_epochs"]:
        raise ValueError("epoch coverage is not supported by request records")
    for c in life:
        exemption = case["mode"] == "shadow" and int(c["epoch"]) == 1
        if bool(int(c["retained_base_exemption"])) != exemption:
            raise ValueError("unexpected lifecycle exemption")
        owner = float(c["owner_released_ms"])
        ok = (float(c["published_ms"]) < end and (exemption or 0 < owner < end) and
              float(c["exclusive_reclaimed_ms"]) < end)
        if ok != bool(int(c["within_window"])):
            raise ValueError("lifecycle coverage flag disagrees with clocks")


def retirement_events(raw, name, case):
    """Diagnostic clock alignment, not a new selection/SLO criterion or ablation."""
    if case["mode"] != "growth":
        return []
    requests = rows(raw/(name+".requests.csv"))
    lookup = {(int(r["epoch"]), r["device_complete_ms"]): (i, r) for i, r in enumerate(requests)}
    out = []
    for m in rows(raw/(name+".maintenance.csv")):
        found = lookup.get((int(m["epoch"])-1, m["last_reader_device_done_ms"]))
        if found is None:
            continue
        index, r = found
        published, owner = float(m["published_ms"]), float(m["old_epoch_owner_released_ms"])
        begin, device, end = (float(r[k]) for k in ("begin_ms", "device_complete_ms", "end_ms"))
        if begin <= published <= end and device <= owner <= end:
            out.append({"case_name": name, "rotation": case["rotation"], "cap_mib": case["cap_mib"],
                        "policy": case["policy"], "maintenance_epoch": int(m["epoch"]), "request_index": index,
                        "request_service_ms": float(r["service_ms"]), "kernel_ms": float(r["kernel_ms"]),
                        "post_gpu_request_ms": end-device, "owner_release_after_gpu_ms": owner-device,
                        "exclusive_reclaim_after_gpu_ms": float(m["exclusive_actual_reclaim_ms"])-device,
                        "request_end_after_owner_release_ms": end-owner})
    return out


def save(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def span(values, digits=3):
    return f"{min(values):.{digits}f}–{max(values):.{digits}f}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--cpu-ready", type=Path, required=True)
    p.add_argument("--dev-manifest", type=Path, required=True)
    p.add_argument("--test-manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    raw = a.raw.resolve()
    complete = json.loads((raw/"COLLECTION_COMPLETE.json").read_text())
    manifest = json.loads((raw/"MANIFEST.json").read_text())
    frozen = json.loads((raw/"FROZEN.json").read_text())
    ready = json.loads(a.cpu_ready.read_text())
    if digest(raw/"FROZEN.json") != complete["frozen_sha256"] or digest(a.cpu_ready) != frozen["cpu_ready_sha256"]:
        raise ValueError("freeze/CPU receipt mismatch")
    if manifest["cpu_ready_sha256"] != frozen["cpu_ready_sha256"]:
        raise ValueError("campaign CPU identity mismatch")
    if manifest["binary_sha256"] != ready["binary_sha256"] or digest(a.cpu_ready.parent/"replay") != ready["binary_sha256"]:
        raise ValueError("executed/retained binary identity mismatch")
    for rel, sha in ready["sources"].items():
        if digest(ROOT/rel) != sha:
            raise ValueError("measured source changed: "+rel)
    for label, file in (("dev", a.dev_manifest), ("test", a.test_manifest)):
        if digest(file) != ready["datasets"][label]["input_hashes"]["MANIFEST.json"]:
            raise ValueError("dataset manifest identity mismatch")
    summaries = {}
    for name in manifest["commands"]:
        process = json.loads((raw/(name+".process.json")).read_text())
        if process["failure"] or process["returncode"]:
            raise ValueError("failed child in completed campaign")
        if any(int(s["gpu"][0][5]) > process["cap_mib"] for s in process["samples"]):
            raise ValueError("NVML sample exceeds declared cap")
        if name.startswith("test_") and process["pre"]["utc"] <= frozen["frozen_utc"]:
            raise ValueError("test ran before parameter freeze")
        if name == "gate_guards":
            continue
        case = summarize(raw/name)
        audit_timeline(raw, name, case)
        recorded = json.loads((raw/(name+".summary.json")).read_text())
        verify_summary(case, recorded)
        summaries[name] = recorded
    for c in frozen["development_cases"]:
        if digest(raw/(c["name"]+".summary.json")) != c["sha256"]:
            raise ValueError("development evidence changed after selection")
    expected = set()
    for cap, config in frozen["configuration"].items():
        calibration = summaries[f"dev_calibrate_cap{cap}"]
        baseline = summaries[f"dev_static_final_cap{cap}"]
        if (config["calibration"] != calibration or config["baseline"] != baseline or
                config["p99_deadline_ms"] != 2*baseline["p99_response_ms"] or
                config["interval_ms"] != interval_for(calibration["mean_service_ms"])):
            raise ValueError("load/deadline not derived from registered development rule")
        dev = [c for n, c in summaries.items() if n.startswith("dev_") and c["mode"] == "growth" and str(c["cap_mib"]) == cap]
        for family in ("periodic", "tier"):
            if config[family] != choose(dev, config["p99_deadline_ms"], family):
                raise ValueError("selection violates registered ranking")
        for rotation in range(4):
            for mode in ("static_base", "static_final"):
                expected.add(f"test_r{rotation}_cap{cap}_{mode}")
            for policy in ("all_delta", config["periodic"], config["tier"], "compact"):
                for mode in ("shadow", "growth"):
                    expected.add(f"test_r{rotation}_cap{cap}_{policy}_{mode}")
    actual = {n for n in summaries if n.startswith("test_")}
    if actual != expected or len(actual) != 80 or complete["test_cases"] != 80:
        raise ValueError("incomplete/extra test matrix")
    tests = []
    for name in sorted(actual):
        c = dict(summaries[name], case_name=name)
        config = frozen["configuration"][str(c["cap_mib"])]
        if c["interval_ms"] != config["interval_ms"]:
            raise ValueError("test arrival rate changed after freeze")
        c["technical_pass"] = passes(c, config["p99_deadline_ms"])
        tests.append(c)
    outcomes, comparisons = {}, []
    retirements = [event for name in sorted(actual) for event in retirement_events(raw, name, summaries[name])]
    for cap, config in frozen["configuration"].items():
        subset = [c for c in tests if str(c["cap_mib"]) == cap]
        baseline_ok = all(c["technical_pass"] for c in subset if c["mode"].startswith("static_"))
        families = {}
        for policy in ("all_delta", config["periodic"], config["tier"], "compact"):
            growth = [c for c in subset if c["mode"] == "growth" and c["policy"] == policy]
            shadow = [c for c in subset if c["mode"] == "shadow" and c["policy"] == policy]
            families[policy] = {"growth_passes": sum(c["technical_pass"] for c in growth),
                                "shadow_passes": sum(c["technical_pass"] for c in shadow)}
            for rotation in range(4):
                g = next(c for c in growth if c["rotation"] == rotation)
                s = next(c for c in shadow if c["rotation"] == rotation)
                b = next(c for c in subset if c["mode"] == "static_base" and c["rotation"] == rotation)
                workload_keys = ("uploaded_bytes", "merged_host_rw_bytes", "merges", "deferred", "end_runs")
                event_keys = ("epoch", "status", "rows", "runs", "merges", "deferred", "uploaded_bytes", "merge_host_rw_bytes")
                growth_events = rows(raw/(g["case_name"]+".maintenance.csv"))
                shadow_events = rows(raw/(s["case_name"]+".maintenance.csv"))
                mismatches = [int(a["epoch"]) for a, b in zip(growth_events, shadow_events)
                              if any(a[k] != b[k] for k in event_keys)]
                comparisons.append({"cap_mib": int(cap), "policy": policy, "rotation": rotation,
                                    "shadow_vs_base_p99_ratio": s["p99_response_ms"]/b["p99_response_ms"],
                                    "shadow_growth_maintenance_equal": not mismatches,
                                    "different_maintenance_epochs": mismatches,
                                    "growth_work": {k: g[k] for k in workload_keys},
                                    "shadow_work": {k: s[k] for k in workload_keys}})
        successful = [policy for policy, v in families.items() if v["growth_passes"] == 4]
        outcomes[cap] = {"all_static_controls_pass": baseline_ok, "policies": families,
                         "growth_successful_policies": successful,
                         "ordinary_sufficient_at_this_load": baseline_ok and bool(successful)}
    stop = all(v["ordinary_sufficient_at_this_load"] for v in outcomes.values())
    result = {"scope": "10M, Q8, tau0.8, finite six releases, one development-calibrated fixed arrival rate per cap",
              "test_cases": tests, "outcomes": outcomes, "shadow_comparisons": comparisons,
              "reader_retirement_diagnostics": retirements,
              "decision": "stop_candidate_ordinary_sufficient_in_registered_scope" if stop else
                          "registered_gate_not_fully_met_no_new_mechanism_authorized",
              "all_test_coverage_pass": all(c["coverage_pass"] for c in tests),
              "checked_test_batches": sum(c["completed_batches"] for c in tests),
              "checked_test_queries": sum(c["completed_batches"]*8 for c in tests)}
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    save(out/"summary.json", result)
    shutil.copyfile(raw/"FROZEN.json", out/"frozen.json")
    for label, source in (("dev", a.dev_manifest), ("test", a.test_manifest)):
        shutil.copyfile(source, out/(label+"_manifest.json"))
    columns = [k for k in tests[0] if k != "seen_epochs"]
    with (out/"cases.csv").open("x") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(tests)
    report = ["# Gate 2 固定到达持续服务结果", "", "本轮只回答登记范围内普通控制是否足够；不推广到生产 SLO 或 41M。", "",
              f"完整测试：80 fresh-process cases，{result['checked_test_queries']:,} 个完整查询结果逐条匹配 CPU oracle。",
              f"六次发布/回收与读覆盖全部通过：{result['all_test_coverage_pass']}。", "",
              "## 冻结负载与选择", "", "| 整卡预算 MiB | 到达 queries/s | p99 门槛 ms | periodic | tier |",
              "|---|---:|---:|---|---|"]
    for cap, c in frozen["configuration"].items():
        report.append(f"| {cap} | {c['offered_queries_per_s']:.1f} | {c['p99_deadline_ms']:.3f} | {c['periodic']} | {c['tier']} |")
    report += ["", "## 实际增长（四个独立进程，区间为 min–max）", "",
               "| 预算 | 策略 | 达标 /4 | 响应 p99 ms | 最低窗口完成率 | 最大发布延迟 ms | 合并次数 |",
               "|---|---|---:|---:|---:|---:|---:|"]
    for cap, c in frozen["configuration"].items():
        for policy in ("all_delta", c["periodic"], c["tier"], "compact"):
            group = [x for x in tests if str(x["cap_mib"]) == cap and x["policy"] == policy and x["mode"] == "growth"]
            report.append(f"| {cap} | {policy} | {sum(x['technical_pass'] for x in group)} | "
                          f"{span([x['p99_response_ms'] for x in group])} | {min(x['completion_fraction'] for x in group):.3%} | "
                          f"{max(x['max_publication_lag_ms'] for x in group):.3f} | {span([x['merges'] for x in group], 0)} |")
    report += ["", "## 静态控制与结论", "", "| 预算 | 静态 arm | 达标 /4 | 响应 p99 ms |", "|---|---|---:|---:|"]
    for cap in frozen["configuration"]:
        for mode in ("static_base", "static_final"):
            group = [x for x in tests if str(x["cap_mib"]) == cap and x["mode"] == mode]
            report.append(f"| {cap} | {mode} | {sum(x['technical_pass'] for x in group)} | {span([x['p99_response_ms'] for x in group])} |")
    report += ["", ("停止本候选：每档预算都有普通策略在四次测试中满足技术门槛，且静态控制通过。" if stop else
                       "登记门槛尚未全部通过。失败不自动说明新算法必要；须结合静态控制、完整工作量和重复性解释。"),
               "", "## 回收路径诊断（不参与调参或达标判定）", ""]
    slow = [e for e in retirements if e["policy"] == "compact" and e["cap_mib"] == 2048 and e["post_gpu_request_ms"] > 5]
    if slow:
        report += [f"2048 MiB compact 的 {len(slow)} 次请求中，旧 epoch owner 在 GPU 完成之后、请求返回之前释放；",
                   f"这些请求的 GPU 后完成段为 {span([e['post_gpu_request_ms'] for e in slow])} ms，kernel 仅为 "
                   f"{span([e['kernel_ms'] for e in slow])} ms，分布于 {len({e['rotation'] for e in slow})} 个独立进程。",
                   "源码中请求末尾同步释放 acquired owner；run/host DB 成员销毁也在该路径上。时钟与这一路径一致，",
                   "支持 CPU 回收/完成段导致排队的解释，而非扫描 kernel 变慢。未做回收线程单变量对照，不能把更细的因果分解当成已验证结论。"]
    else:
        report += ["本轮没有观察到满足该时钟对齐条件且 GPU 后完成段 >5 ms 的 roomy compact 请求；不据此排除其他尾延迟原因。"]
    report += [
               "", "开发/测试 ID 不相交，但共享历史日期；测试集在 Gate 1 已被观察。仅一个负载点、64 个 cohort 查询、六次更新。",
               "六次真实历史增量被压缩到固定 8 秒实验窗口；这不是自然业务更新频率，也不是稳态证明。",
               "shadow 固定 base；growth 增加可见行数。受限预算下 shadow 留住 base 可能改变合并工作量，不能直接作等工作量因果对照。",
               "CPU oracle 在窗口后检查；所有请求从预定到达计算响应，排空结果未从分母移除。显存为整卡采样观测上限，不是硬件分区。", ""]
    (out/"REPORT.md").write_text("\n".join(report))
    receipt = {"source_hashes": ready["sources"], "analysis_sha256": digest(Path(__file__)),
               "reanalysis_tolerance": {"mean_service_ms": "abs/rel 1e-12; Python float sum version difference", "other_fields": "exact"},
               "binary_sha256": ready["binary_sha256"], "cpu_ready_sha256": digest(a.cpu_ready),
               "frozen_sha256": digest(raw/"FROZEN.json"), "gpu_uuid": manifest["gpu_uuid"],
               "raw_files": {str(f.relative_to(raw)): digest(f) for f in sorted(raw.iterdir()) if f.is_file()},
               "result_files": {f.name: digest(f) for f in sorted(out.iterdir()) if f.is_file()}}
    save(out/"evidence_receipt.json", receipt)
    print(json.dumps({"decision": result["decision"], "outcomes": outcomes, "queries": result["checked_test_queries"]}, indent=2))


if __name__ == "__main__":
    main()
