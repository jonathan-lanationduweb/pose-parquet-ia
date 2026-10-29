"""Synthetic fixtures only: no real annotation is created or approved by tests."""

import copy
import hashlib
import json
import time
from threading import Lock
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from scripts.foreground_annotation_v6 import SCHEMA, masks, store_record, validate
from scripts.foreground_evaluation_v6 import (
    EvaluationRunner,
    classify,
    evaluate,
    fp_budget,
    gt_fingerprint,
    load_human,
    pixel_metrics,
    readiness,
)
from scripts.foreground_local_experiment_v6 import automatic_rois, proposal_consensus, run_local
from scripts.foreground_proposals_v6 import ProposalBank


def setup(tmp_path, labels=True):
    sources = tmp_path / "sources"
    source = sources / "sofa"
    source.mkdir(parents=True)
    photo = source / "01-original.png"
    Image.new("RGB", (32, 24), (190, 180, 160)).save(photo)
    scene = {
        "id": "sofa",
        "width": 32,
        "height": 24,
        "sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
    }
    fg = np.zeros((24, 32), bool)
    fg[5:19, 7:12] = True
    semantic = np.full(fg.shape, 3, np.int32)
    if labels:
        semantic[fg] = 19
    np.save(source / "labels.npy", semantic)
    np.save(source / "support.npy", np.ones_like(fg))
    baseline = tmp_path / "foreground-mask-v5-1/sofa"
    baseline.mkdir(parents=True)
    np.save(baseline / "v51.npy", fg if labels else np.zeros_like(fg))
    np.save(baseline / "prior.npy", fg if labels else np.zeros_like(fg))
    return sources, scene, ProposalBank(sources), tmp_path / "human", fg


def manual(scene):
    return {
        "schema": SCHEMA,
        "scene": scene["id"],
        "sourceSha256": scene["sha256"],
        "width": 32,
        "height": 24,
        "status": "draft",
        "humanConfirmed": False,
        "annotator": "SYNTHETIC TEST — NOT HUMAN GT",
        "emptySceneConfirmed": False,
        "objects": [
            {
                "id": "synthetic-object",
                "category": "chair",
                "reviewed": False,
                "humanConfirmed": False,
                "annotationMode": "manual",
                "region": [3, 2, 20, 22],
                "drawings": [
                    {
                        "kind": "polygon",
                        "mode": "foreground",
                        "radius": 1,
                        "points": [[7, 5], [12, 5], [12, 19], [7, 19]],
                    }
                ],
                "notes": "synthetic",
            }
        ],
    }


def approve(record):
    record = copy.deepcopy(record)
    for obj in record["objects"]:
        obj.update(reviewed=True, humanConfirmed=True)
    return record


def save(record, scene, bank, private):
    return store_record(validate(record, scene), scene, private, bank, Lock())


def test_assisted_proposal_and_acceptance_are_not_gt(tmp_path):
    sources, scene, bank, private, fg = setup(tmp_path)
    before = bank.public(scene)
    assert before
    assert not private.exists()
    p = before[0]
    record = manual(scene)
    obj = record["objects"][0]
    obj.update(
        annotationMode="assisted-review",
        useProposal=True,
        drawings=[],
        proposal={k: p[k] for k in ["id", "hash", "source"]},
        region=p["region"],
    )
    draft = save(record, scene, bank, private)
    assert draft["maskRevision"] is None
    assert not list(private.rglob("*.png"))
    assert readiness(load_human(private, sources)[0])["objects"] == 0
    result = save(approve(record), scene, bank, private)
    assert result["objects"][0]["humanReviewed"] is True
    assert result["objects"][0]["humanDrawnFromScratch"] is False
    assert result["objects"][0]["proposalSource"] == "foreground-v5-1"
    assert result["humanConfirmed"] is True
    loaded, errors = load_human(private, sources)
    assert not errors
    np.testing.assert_array_equal(loaded[0]["entries"][0]["gt"], fg)


def test_proposal_corrections_and_uncertain_exclusion(tmp_path):
    _, scene, bank, _, _ = setup(tmp_path)
    p = bank.public(scene)[0]
    record = manual(scene)
    obj = record["objects"][0]
    obj.update(
        annotationMode="assisted-review",
        useProposal=True,
        proposal={k: p[k] for k in ["id", "hash", "source"]},
        drawings=[
            {
                "kind": "polygon",
                "mode": "erase",
                "radius": 1,
                "points": [[7, 5], [9, 5], [9, 10], [7, 10]],
            },
            {"kind": "brush", "mode": "uncertain", "radius": 0.5, "points": [[10.5, 15.5]]},
        ],
    )
    fg, valid, uncertain = masks(record, obj, bank.resolve(scene, obj))
    assert not fg[6, 8] and valid[6, 8]
    assert uncertain[15, 10] and not fg[15, 10] and not valid[15, 10]
    assert fg[12, 10]


def test_stale_proposal_and_ai_draft_cannot_be_promoted(tmp_path):
    _, scene, bank, private, _ = setup(tmp_path)
    p = bank.public(scene)[0]
    record = manual(scene)
    record["objects"][0].update(
        annotationMode="assisted-review",
        useProposal=True,
        drawings=[],
        proposal={"id": p["id"], "hash": "wrong", "source": p["source"]},
    )
    with pytest.raises(ValueError, match="périmée"):
        save(approve(record), scene, bank, private)
    assert not private.exists()


def test_partial_validation_keeps_other_objects_as_drafts(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    other = copy.deepcopy(record["objects"][0])
    other.update(id="pending", humanConfirmed=False, reviewed=False)
    record["objects"].append(other)
    result = save(record, scene, bank, private)
    assert result["status"] == "partial-reviewed" and not result["humanConfirmed"]
    assert result["validatedObjectIds"] == ["synthetic-object"]
    loaded, errors = load_human(private, sources)
    assert not errors
    assert readiness(loaded)["objects"] == 1
    assert not list(private.rglob("pending.foreground.png"))


def test_gt_file_tampering_and_source_change_are_rejected(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path)
    result = save(approve(manual(scene)), scene, bank, private)
    mask = private / "sofa/revisions" / result["maskRevision"] / "synthetic-object.foreground.png"
    original = mask.read_bytes()
    Image.new("L", (32, 24)).save(mask)
    loaded, errors = load_human(private, sources)
    assert not loaded and errors
    mask.write_bytes(original)
    Image.new("RGB", (32, 24), (1, 2, 3)).save(sources / "sofa/01-original.png")
    loaded, errors = load_human(private, sources)
    assert not loaded and errors


def test_background_in_review_roi_is_required(tmp_path):
    _, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    record["objects"][0]["region"] = [7, 5, 12, 19]
    with pytest.raises(ValueError, match="Agrandissez"):
        save(record, scene, bank, private)


def test_negative_regions_count_without_inventing_foreground(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    record["objects"][0].update(category="negative-region", drawings=[], region=[20, 2, 30, 22])
    save(record, scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors
    gate = readiness(loaded)
    assert gate["objects"] == 0 and gate["negativeRegions"] == 1 and not gate["ready"]
    assert not loaded[0]["gt"].any()


def test_metrics_exclude_unknown_and_unreviewed_pixels():
    gt = np.zeros((8, 8), bool)
    gt[2:4, 2:4] = True
    valid = np.zeros_like(gt)
    valid[1:5, 1:5] = True
    valid[2, 2] = False
    pred = gt.copy()
    pred[0, :] = True
    pred[2, 2] = False
    pred[4, 4] = True
    result = pixel_metrics(pred, gt, valid)
    assert result["tp"] == 3 and result["fp"] == 1 and result["fn"] == 0
    assert result["recall"] == 1 and result["precision"] == 0.75
    assert result["gtArea"] == 3


@pytest.mark.parametrize(
    "recall,case",
    [
        (None, "NEGATIVE_REGION"),
        (0, "NO_SEED"),
        (0.099, "NO_SEED"),
        (0.1, "PARTIAL_SEED"),
        (0.899, "PARTIAL_SEED"),
        (0.9, "GOOD_SEED"),
        (1, "GOOD_SEED"),
    ],
)
def test_abc_is_analytical_only(recall, case):
    assert classify(recall) == case


def test_readiness_minimum_requires_five_three_and_negative():
    def entry(category):
        return {"object": {"category": category}, "valid": np.ones((2, 2), bool)}

    items = [entry(c) for c in ["sofa", "chair", "rug", "chair", "sofa"]]
    assert not readiness([{"entries": items}])["ready"]
    assert readiness([{"entries": items + [entry("negative-region")]}])["ready"]
    assert not readiness([{"entries": items[:4] + [entry("negative-region")]}])["ready"]


def test_local_consensus_rejects_floor_hallucination_and_class_instability():
    domain = np.ones((100, 100), bool)
    coarse = np.zeros_like(domain)
    all_rug = np.full(domain.shape, 28, np.int32)
    accepted, _ = proposal_consensus([all_rug, all_rug], domain, coarse)
    assert not accepted.any()
    a = np.full(domain.shape, -1, np.int32)
    a[40:44, 40:44] = 19
    b = a.copy()
    b[40:44, 40:44] = 28
    assert not proposal_consensus([a, b], domain, coarse)[0].any()
    accepted, report = proposal_consensus([a, a], domain, coarse)
    assert accepted.sum() == 16 and report["confidenceCalibrated"] is False
    assert not proposal_consensus([a], domain, coarse)[0].any()


def test_false_positive_budget_rejects_small_tp_large_fp():
    before = np.zeros((100, 100), bool)
    truth = before.copy()
    truth[2:5, 2:5] = True
    after = np.ones_like(before)
    valid = np.ones_like(before)
    assert fp_budget(before, after, truth, valid)["accepted"] is False
    assert fp_budget(before, truth, truth, valid)["accepted"] is True


def test_roi_and_empty_pass_use_no_gt_and_preserve_baseline():
    rgb = np.full((40, 60, 3), 180, np.uint8)
    domain = np.ones((40, 60), bool)
    coarse = np.zeros_like(domain)
    baseline = coarse.copy()
    baseline[4:6, 5:7] = True

    def forbidden(_):
        raise AssertionError("Uniform scene should skip local inference")

    result = run_local(rgb, domain, coarse, baseline, baseline, SimpleNamespace(segment=forbidden))
    np.testing.assert_array_equal(result["candidateMask"], baseline)
    assert not result["rois"] and not result["gtUsedForRoi"]
    assert automatic_rois(rgb, np.zeros_like(domain), coarse) == []


def test_worker_resumes_automatically_only_when_human_minimum_exists(tmp_path, monkeypatch):
    sources, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    categories = ["sofa", "chair", "rug", "chair", "sofa", "negative-region"]
    template = record["objects"][0]
    record["objects"] = []
    for index, category in enumerate(categories):
        obj = copy.deepcopy(template)
        obj.update(id="synthetic-" + str(index), category=category)
        if category == "negative-region":
            obj.update(drawings=[], region=[20, 2, 30, 22])
        record["objects"].append(obj)
    called = []

    def fake(loaded, _sources, output):
        called.append(readiness(loaded))
        output.mkdir(parents=True, exist_ok=True)
        report = {
            "verdict": "V6_PRELIMINARY_HUMAN_GT_ANALYZED",
            "caseCounts": {},
            "label": "PRELIMINARY HUMAN GT",
        }
        (output / "metrics.json").write_text(json.dumps(report), encoding="utf8")
        return report

    monkeypatch.setattr("scripts.foreground_evaluation_v6.evaluate", fake)
    runner = EvaluationRunner(private, sources, tmp_path / "report")
    runner.queue()
    for _ in range(100):
        if not runner.running:
            break
        time.sleep(0.02)
    assert not called and runner.snapshot()["status"] == "waiting"
    save(record, scene, bank, private)
    runner.queue()
    for _ in range(200):
        if not runner.running:
            break
        time.sleep(0.02)
    assert len(called) == 1 and runner.snapshot()["status"] == "complete"
    runner.queue()
    for _ in range(100):
        if not runner.running:
            break
        time.sleep(0.02)
    assert len(called) == 1  # unchanged human revision does not repeat experiments
    runner.pool.shutdown(wait=True)


def test_measured_no_seed_calls_targeted_experiment_not_gt_roi(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path, labels=False)
    save(approve(manual(scene)), scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors
    calls = []

    def fake(rgb, domain, coarse, prior, baseline):
        calls.append((rgb.shape, domain.shape, coarse.any(), prior.any()))
        # Synthetic oracle double exercises metric plumbing, not an evaluated method.
        candidate = baseline.copy()
        candidate[5:19, 7:12] = True
        return {
            "candidateMask": candidate,
            "additions": candidate,
            "mergedSeeds": candidate,
            "calls": [],
            "gates": [],
            "timingsMs": {},
            "gtUsedForRoi": False,
        }

    result = evaluate(loaded, sources, tmp_path / "report", local_runner=fake)
    assert calls and result["objects"][0]["case"] == "NO_SEED"
    assert result["objects"][0]["v6Candidate"]["recall"] == 1
    assert result["objects"][0]["delta"]["addedFP"] == 0
    assert result["productionIntegrated"] is False


def test_good_seed_skips_local_experiment(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path)
    save(approve(manual(scene)), scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors

    def forbidden(*_args):
        raise AssertionError("GOOD_SEED must skip local inference")

    result = evaluate(loaded, sources, tmp_path / "report", local_runner=forbidden)
    assert result["caseCounts"]["GOOD_SEED"] == 1
    assert result["localExperiments"] == []
    assert result["byCategory"]["chair"]["coarse"]["recall"]["mean"] == 1


def test_local_experiment_also_checks_negative_scene(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path, labels=False)
    record = approve(manual(scene))
    save(record, scene, bank, private)
    negative_source = sources / "empty-room"
    negative_source.mkdir()
    photo = negative_source / "01-original.png"
    Image.new("RGB", (32, 24), (150, 150, 150)).save(photo)
    negative_scene = {
        **scene,
        "id": "empty-room",
        "sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
    }
    np.save(negative_source / "labels.npy", np.full((24, 32), 3, np.int32))
    np.save(negative_source / "support.npy", np.ones((24, 32), bool))
    baseline = sources.parent / "foreground-mask-v5-1/empty-room"
    baseline.mkdir()
    for name in ["v51.npy", "prior.npy"]:
        np.save(baseline / name, np.zeros((24, 32), bool))
    record = approve(manual(negative_scene))
    record["objects"][0].update(category="negative-region", drawings=[])
    save(record, negative_scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors
    calls = []

    def fake(rgb, _domain, _coarse, _prior, base):
        calls.append(rgb[0, 0, 0])
        candidate = base.copy()
        if rgb[0, 0, 0] == 190:
            candidate[5:19, 7:12] = True
        return {
            "candidateMask": candidate,
            "additions": candidate,
            "mergedSeeds": candidate,
            "calls": [],
            "gates": [],
            "timingsMs": {},
            "gtUsedForRoi": False,
        }

    result = evaluate(loaded, sources, tmp_path / "report", local_runner=fake)
    assert len(calls) == 2
    control = next(e for e in result["localExperiments"] if e["scene"] == "empty-room")
    assert control["budget"]["controlOnly"] and control["budget"]["accepted"]
    assert control["budget"]["addedFP"] == 0


def test_unapproved_draft_edits_do_not_change_evaluation_fingerprint(tmp_path):
    sources, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    save(record, scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors
    first = gt_fingerprint(loaded, sources)
    record["objects"].append(
        {
            **copy.deepcopy(record["objects"][0]),
            "id": "pending-only",
            "reviewed": False,
            "humanConfirmed": False,
        }
    )
    save(record, scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors
    assert gt_fingerprint(loaded, sources) == first


def test_negative_region_cannot_contradict_validated_object(tmp_path):
    _, scene, bank, private, _ = setup(tmp_path)
    record = approve(manual(scene))
    negative = copy.deepcopy(record["objects"][0])
    negative.update(id="negative-over-object", category="negative-region", drawings=[])
    record["objects"].append(negative)
    with pytest.raises(ValueError, match="recouvre"):
        save(record, scene, bank, private)
    assert not private.exists()


@pytest.mark.parametrize(
    "coverage,expected",
    [(False, "V6_PRELIMINARY_HUMAN_GT_ANALYZED"), (True, "V6_SECOND_MODEL_EVALUATION_REQUIRED")],
)
def test_second_model_requires_actual_local_coverage_and_raw_failure(tmp_path, coverage, expected):
    sources, scene, bank, private, _ = setup(tmp_path, labels=False)
    record = approve(manual(scene))
    other = copy.deepcopy(record["objects"][0])
    other.update(id="other-synthetic-category", category="sofa")
    record["objects"].append(other)
    save(record, scene, bank, private)
    loaded, errors = load_human(private, sources)
    assert not errors

    def fake(_rgb, _domain, _coarse, _prior, base):
        box = [0, 0, 32, 24] if coverage else [20, 0, 32, 8]
        return {
            "candidateMask": base.copy(),
            "additions": np.zeros_like(base),
            "rawForeground": np.zeros_like(base),
            "mergedSeeds": base.copy(),
            "calls": [{"box": box}, {"box": box}],
            "gates": [],
            "timingsMs": {},
            "gtUsedForRoi": False,
        }

    result = evaluate(loaded, sources, tmp_path / "report", local_runner=fake)
    assert result["verdict"] == expected
