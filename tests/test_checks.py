"""The checks check themselves: each test breaks something on purpose and expects
the right check to catch it. Run with:  python3 -m unittest discover -s tests -v
"""
import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import dc  # noqa: E402
import validate  # noqa: E402
import verify_media  # noqa: E402
import new_episode  # noqa: E402
import build_prompts  # noqa: E402
import verify_voice  # noqa: E402
import topics  # noqa: E402
import check_episode  # noqa: E402
import script_review  # noqa: E402
try:
    import build_reel  # noqa: E402  (needs Pillow and numpy)
except ImportError:
    build_reel = None

PILOT = ROOT / "episodes" / "ep01-claim-reject"
# Someone allowed to approve: the first name in brand/brand.json approvers (approve.py refuses anyone else)
PERSON = (dc.brand().get("approvers") or ["Tester"])[0]


def sourced_ids(ep):
    """The pilot's facts and rules: everything a person checks against its source."""
    return [d["id"] for d in ep["data"] if d["kind"] in dc.SOURCED_KINDS]


class EpisodeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ep_dir = self.tmp / PILOT.name
        shutil.copytree(PILOT, self.ep_dir)
        self.ep = dc.load_json(self.ep_dir / "episode.json")
        self.status = dc.load_json(self.ep_dir / "status.json")
        # the real pilot moves on as people check and approve it; every test starts from before any of that
        for d in self.ep["data"]:
            if d["kind"] in dc.SOURCED_KINDS:
                d["checked_by"] = d["checked_on"] = None
                d.pop("check_result", None)
        self.status["steps"] = dc.load_json(ROOT / "templates" / "status.template.json")["steps"]
        self.status["post"] = {"url": None, "posted_at": None}
        (self.ep_dir / "posted.json").unlink(missing_ok=True)       # and before it was posted
        self.save(rebuild_prompts=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save(self, rebuild_prompts=True):
        dc.save_json(self.ep_dir / "episode.json", self.ep)
        dc.save_json(self.ep_dir / "status.json", self.status)
        if rebuild_prompts:
            import build_prompts
            (self.ep_dir / "prompts.md").write_text(build_prompts.render(self.ep_dir), encoding="utf-8")
            (self.ep_dir / "prompts-writing.md").write_text(build_prompts.render_writing(self.ep_dir), encoding="utf-8")

    def run_checks(self):
        r, _, _ = validate.validate_episode(self.ep_dir, dc.brand())
        return r

    def fail_ids(self, r):
        return {i["id"] for i in r.of("fail")}

    def shot(self, sid):
        return next(s for s in self.ep["shots"] if s["id"] == sid)

    def line(self, sid):
        return next(l for l in self.ep["script"] if l["shot"] == sid)

    def approve(self, step_id, by=PERSON):
        content = dc.locked_content(self.ep, step_id)
        self.status["steps"][step_id] = {"state": "passed", "notes": "",
                                         "approval": {"by": by, "at": "2026-11-11T10:00:00",
                                                      "hash": dc.section_hash(content) if content is not None else None}}

    def check_facts(self):
        for d in self.ep["data"]:
            if d["kind"] in dc.SOURCED_KINDS:
                d["checked_by"], d["checked_on"] = PERSON, "2026-11-11"


class TestContentChecks(EpisodeCase):
    def test_pilot_has_no_failures(self):
        self.assertEqual(self.run_checks().of("fail"), [])

    def test_invented_number_in_voice_is_caught(self):
        self.line("S04")["vo"] = self.line("S04")["vo"].replace("₹2,00,000", "₹2,10,000")
        self.line("S04")["highlights"] = ["₹2,10,000"]
        self.save()
        self.assertIn("E3.5", self.fail_ids(self.run_checks()))

    def test_wrong_derived_value_is_caught(self):
        next(d for d in self.ep["data"] if d["id"] == "total_pf")["value"] = 210000
        self.save()
        self.assertIn("E2.2", self.fail_ids(self.run_checks()))

    def test_western_digit_grouping_is_caught(self):
        sh = self.shot("S04")
        sh["card_text"] = [t.replace("2,00,000", "200,000") for t in sh["card_text"]]
        self.save()
        self.assertIn("E4.3", self.fail_ids(self.run_checks()))

    def test_card_text_missing_from_prompt_is_caught(self):
        # an episode on the older AI-image route (no reel.json) must quote its card text in the keyframe prompt
        (self.ep_dir / "reel.json").unlink()
        self.ep.pop("route", None)
        sh = self.shot("S01")
        sh["keyframe_prompt"] = "A photo, a stamp and a black card: CLAIM STATUS, " + ", ".join(
            '"{}"'.format(t) for t in sh["card_text"] if t != "CLAIM STATUS")
        self.save()
        self.assertIn("E4.4", self.fail_ids(self.run_checks()))

    def test_build_route_needs_no_keyframe_prompts(self):
        for sh in self.ep["shots"]:
            for key in ("keyframe_prompt", "motion_prompt", "assets", "canva", "sfx"):
                sh.pop(key, None)
        self.save()
        self.assertEqual(self.fail_ids(self.run_checks()), set())

    def test_written_content_is_checked_even_when_its_step_is_todo(self):
        for step in self.status["steps"].values():
            step["state"] = "todo"
        self.line("S04")["vo"] = self.line("S04")["vo"].replace("₹2,00,000", "₹2,20,000")
        self.save()
        self.assertIn("E3.5", self.fail_ids(self.run_checks()))

    def test_unlabelled_example_number_is_caught(self):
        self.line("S03")["vo"] = "Passbook mein aapka hissa ₹1,50,000, company ka ₹50,000."
        sh = self.shot("S03")
        sh["card_text"] = [t.replace(" (MAAN LO)", "") for t in sh["card_text"]]
        self.save()
        self.assertIn("E3.9", self.fail_ids(self.run_checks()))

    def test_gap_in_timeline_is_caught(self):
        self.shot("S02")["start"] = self.shot("S01")["end"] + 0.5
        self.save()
        self.assertIn("E4.1", self.fail_ids(self.run_checks()))

    def test_stale_prompt_file_is_caught(self):
        self.line("S01")["tts"] = "changed"
        self.save(rebuild_prompts=False)
        self.assertIn("E4.10", self.fail_ids(self.run_checks()))

    def test_wrong_signoff_is_caught(self):
        signoff = next(l for l in self.ep["script"] if l["chapter"] == "signoff")
        signoff["vo"] = "Yeh hai PF Guru Ji."
        signoff["highlights"] = ["PF Guru Ji"]
        self.save()
        self.assertIn("E3.8", self.fail_ids(self.run_checks()))

    def test_a_form_that_isnt_in_the_forms_list_is_caught(self):
        # Form 19 is the PF final settlement form; a reel may only name forms in brand/epfo-forms.json
        line = next(l for l in self.ep["script"] if "Form 19" in l["vo"])
        line["vo"] = line["vo"].replace("Form 19", "Form 21")
        line["highlights"] = ["Form 21"]
        sh = self.shot(line["shot"])
        sh["card_text"] = [t.replace("FORM 19", "FORM 21") for t in sh["card_text"]]
        self.save()
        ids = self.fail_ids(self.run_checks())
        self.assertIn("E3.14", ids)
        self.assertIn("E4.11", ids)
        self.assertNotIn("E3.5", ids)          # a form's name isn't an amount


class TestGates(EpisodeCase):
    def test_approval_goes_stale_when_content_changes(self):
        self.approve("01-brief")
        self.save()
        self.assertNotIn("G5", self.fail_ids(self.run_checks()))
        self.ep["brief"]["hook"] = "Something else."
        self.save()
        self.assertIn("G5", self.fail_ids(self.run_checks()))

    def test_steps_must_pass_in_order(self):
        self.approve("01-brief")
        self.approve("03-script")
        self.save()
        self.assertIn("G2", self.fail_ids(self.run_checks()))

    def test_an_ai_cannot_approve_a_human_step(self):
        self.approve("01-brief", by="Muse")
        self.save()
        self.assertIn("G4", self.fail_ids(self.run_checks()))

    def test_data_cannot_pass_with_unchecked_facts(self):
        self.approve("01-brief")
        self.approve("02-data")
        self.save()
        self.assertIn("G3", self.fail_ids(self.run_checks()))

    def test_full_approval_chain_passes(self):
        self.check_facts()
        for s in ("01-brief", "02-data", "03-script"):
            self.approve(s)
        self.approve("04-shots", by="auto-check")
        self.save()
        self.assertEqual(self.run_checks().of("fail"), [])


class TestApproveTool(EpisodeCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools" / "approve.py")] + list(args),
                              capture_output=True, text=True)

    def test_approve_flow_and_refusals(self):
        ep = str(self.ep_dir)
        first = self.cli("step", ep, "01-brief", "--by", PERSON)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        refused = self.cli("step", ep, "02-data", "--by", PERSON)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("waiting", refused.stdout)
        ids = sourced_ids(self.ep)
        self.assertNotEqual(self.cli("fact", ep, ids[0], "--by", "Muse").returncode, 0)
        self.assertNotEqual(self.cli("fact", ep, "total_pf", "--by", PERSON).returncode, 0, "a derived value has no source to check")
        for fid in ids:                       # every fact and every rule, each by a person
            self.assertEqual(self.cli("fact", ep, fid, "--by", PERSON).returncode, 0, fid)
        self.assertEqual(self.cli("step", ep, "02-data", "--by", PERSON).returncode, 0)
        self.assertNotEqual(self.cli("step", ep, "04-shots").returncode, 0, "04 can't pass before 03")
        self.assertEqual(self.cli("step", ep, "03-script", "--by", PERSON).returncode, 0)
        self.assertEqual(self.cli("step", ep, "04-shots").returncode, 0)
        status = dc.load_json(self.ep_dir / "status.json")
        self.assertEqual(status["steps"]["04-shots"]["state"], "passed")
        # editing the script now breaks the chain until it is approved again
        ep_json = dc.load_json(self.ep_dir / "episode.json")
        ep_json["script"][0]["tts"] = "changed"
        dc.save_json(self.ep_dir / "episode.json", ep_json)
        r, _, _ = validate.validate_episode(self.ep_dir, dc.brand())
        self.assertIn("G5", {i["id"] for i in r.of("fail")})


class TestLoopGuards(EpisodeCase):
    """The guards that keep a fix-and-recheck loop honest."""

    def item(self, iid):
        return next(d for d in self.ep["data"] if d["id"] == iid)

    def test_a_fact_signed_off_by_an_ai_still_waits_for_a_person(self):
        fid = next(d["id"] for d in self.ep["data"] if d["kind"] == "fact")
        self.item(fid).update({"checked_by": "Muse", "checked_on": "2026-11-12"})
        self.save()
        pending = [i for i in self.run_checks().of("pending") if i["id"] == "E2.3" and "'{}'".format(fid) in i["msg"]]
        self.assertTrue(pending and "only a person" in pending[0]["msg"])
        self.item(fid).update({"checked_by": "Asha", "checked_on": "2026-11-12"})
        self.save()
        self.assertFalse([i for i in self.run_checks().of("pending") if "'{}'".format(fid) in i["msg"]])

    def test_a_rule_needs_a_source_and_a_person(self):
        rid = next(d["id"] for d in self.ep["data"] if d["kind"] == "rule")
        self.item(rid).update({"checked_by": "Muse", "checked_on": "2026-11-12"})
        self.save()
        pending = [i for i in self.run_checks().of("pending") if "rule '{}'".format(rid) in i["msg"]]
        self.assertTrue(pending and "only a person" in pending[0]["msg"])
        self.item(rid)["source_url"] = ""
        self.save()
        self.assertTrue(any("rule '{}' needs a source".format(rid) in i["msg"] for i in self.run_checks().of("fail")))
        self.item(rid).pop("statement")
        self.save()
        self.assertTrue(any("rule '{}' needs a statement".format(rid) in i["msg"] for i in self.run_checks().of("fail")))

    def test_voice_text_must_say_the_captions_numbers(self):
        line = next(l for l in self.ep["script"] if "₹1,50,000" in l["vo"])
        line["tts"] = line["tts"].replace("डेढ़ लाख", "ढाई लाख")
        self.save()
        msgs = [i["msg"] for i in self.run_checks().of("fail") if i["id"] == "E3.13"]
        self.assertTrue(any("1,50,000" in m and "doesn't say" in m for m in msgs))
        self.assertTrue(any("2,50,000" in m for m in msgs))
        line["tts"] = line["tts"].replace("ढाई लाख", "एक लाख पचास हज़ार")   # a respelling that keeps the number is fine
        self.save()
        self.assertNotIn("E3.13", self.fail_ids(self.run_checks()))

    def test_a_rate_on_the_caption_must_be_said_in_the_voice(self):
        line = next(l for l in self.ep["script"] if l["shot"] == "S10")
        self.ep["data"].append({"id": "test_rate", "label": "a rate", "kind": "fact", "value": 0.0825, "unit": "%",
                                "source": "test", "source_url": "https://www.pib.gov.in/", "check_note": "test",
                                "checked_by": None, "checked_on": None})
        line["uses"] = line.get("uses", []) + ["test_rate"]
        line["vo"] += " Byaaj 8.25%."
        line["tts"] += " ब्याज आठ पॉइंट दो परसेंट।"                   # 8.2, not 8.25
        self.save()
        msgs = [i["msg"] for i in self.run_checks().of("fail") if i["id"] == "E3.13"]
        self.assertTrue(any("8.25" in m and "doesn't say" in m for m in msgs), msgs)
        line["tts"] = line["tts"].replace("आठ पॉइंट दो परसेंट", "आठ पॉइंट दो पाँच परसेंट")
        self.save()
        self.assertNotIn("E3.13", self.fail_ids(self.run_checks()))

    def test_report_result_fix_then_waiting(self):
        import check_episode
        rep, text = check_episode.check(self.ep_dir, use_voice=False, use_ocr=False)
        self.assertEqual(rep.result(), "WAITING")                          # only the facts and rules a person checks are left
        self.assertIn("**RESULT: WAITING**", text)
        self.assertTrue(any(p["area"] == "Rule" for p in rep.person))
        line = next(l for l in self.ep["script"] if "₹2,00,000" in l["vo"])
        line["vo"] = line["vo"].replace("₹2,00,000", "₹2,20,000")
        self.save()
        rep, text = check_episode.check(self.ep_dir, use_voice=False, use_ocr=False)
        self.assertEqual(rep.result(), "FIX")
        self.assertTrue(any(f["where"] == "E3.5" and "₹2,20,000" in f["what"] for f in rep.fix))
        self.assertIn("Fix: ", text)

    def test_an_out_of_date_reel_is_not_failed(self):
        (self.ep_dir / "build").mkdir(exist_ok=True)
        dc.save_json(self.ep_dir / "build" / "timeline.json", {"inputs": "0000000000000000", "length": 1, "shots": []})
        res = verify_media.check_final(self.ep_dir, self.ep_dir / "media" / "final" / "none.mp4")
        self.assertTrue(res.out_of_date)
        self.assertFalse(res.failed)

    def test_half_numbers(self):
        self.assertEqual(verify_voice.spoken_numbers("यानी ढाई हज़ार का कस्टमर"), [2500])
        self.assertEqual(verify_voice.spoken_numbers("डेढ़ लाख रुपये"), [150000])


class TestNewEpisodeFlow(unittest.TestCase):
    """What Muse uploads in MUSE.md → A new episode, stage by stage, with GitHub's --prepare in between."""

    def test_brief_then_script_then_shots(self):
        src = dc.load_json(PILOT / "episode.json")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(topics, "DONE_FILE", Path(tmp) / "none.json"):   # no reels made elsewhere
            ep_dir = Path(tmp) / "ep99-flow-test"
            ep_dir.mkdir()
            ep = dc.load_json(ROOT / "templates" / "episode.template.json")
            ep.update({"id": "ep99", "slug": "flow-test", "title": src["title"], "tag": "PF GURU JI #99 · FLOW TEST",
                       "created": "2026-11-12", "brief": src["brief"], "data": src["data"]})

            def stage():
                dc.save_json(ep_dir / "episode.json", ep)
                new_episode.prepare(ep_dir)
                r, _, _ = validate.validate_episode(ep_dir, dc.brand())
                return {i["id"] for i in r.of("fail")}

            self.assertEqual(stage(), set())                                   # N2: brief and data
            self.assertTrue((ep_dir / "status.json").exists())
            ep["script"], ep["post"] = src["script"], src["post"]
            self.assertEqual(stage(), set())                                   # N3: script
            self.assertIn("Step 4 · Shots and reel.json prompt", (ep_dir / "prompts-writing.md").read_text(encoding="utf-8"))
            self.assertTrue((ep_dir / "script.md").exists())                    # the page the person reads
            self.assertEqual(script_review.status(ep_dir)["state"], "waiting")   # nothing is made until they approve
            dc.save_json(ep_dir / "script-approved.json", {
                "version": script_review.version(ep), "approved_by": dc.brand()["approvers"][0],
                "approved_on": "2026-11-16", "their_words": "script OK"})
            self.assertEqual(script_review.status(ep_dir)["state"], "approved")
            keep = ("id", "start", "end", "chapter", "on_screen", "card_text", "motion_text", "uses", "yellow_elements")
            ep["shots"] = [{k: sh[k] for k in keep if k in sh} for sh in src["shots"]]
            ep["breaks"] = src["breaks"]
            self.assertEqual(stage(), set())                                   # N4: shots, no keyframe prompts needed
            self.assertIn(ep["shots"][-1]["id"], dc.load_json(ep_dir / "status.json")["shots"])
            self.assertEqual(script_review.status(ep_dir)["state"], "approved")  # shots don't touch the approval
            ep["script"][3]["vo"] = ep["script"][3]["vo"].replace("₹2,00,000", "₹2,20,000")
            self.assertIn("E3.5", stage())                                     # an invented number is still caught
            self.assertEqual(script_review.status(ep_dir)["state"], "changed")   # and the script goes back to the person


class TestNewEpisode(unittest.TestCase):
    def test_new_episode_skeleton_passes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            done = mock.patch.object(topics, "DONE_FILE", tmp / "none.json")         # no reels made elsewhere
            done.start()
            self.addCleanup(done.stop)
            folder = new_episode.create("ep99", "test-topic", "Test topic?", base=tmp)
            r, _, _ = validate.validate_episode(folder, dc.brand())
            self.assertEqual(r.of("fail"), [])
            self.assertIn("01-brief", r.next_action)
            self.assertEqual(dc.load_json(folder / "episode.json")["tag"], "PF GURU JI #99 · TEST TOPIC")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMatching(unittest.TestCase):
    def test_numbers_are_read_the_indian_way(self):
        got = [n["canon"] for n in dc.extract_numbers("₹15,000 mein 1 lakh views, 3% ne, 1,00,000 aur 18% CTR")]
        self.assertEqual(got, ["₹15000", "100000", "3%", "100000", "18%"])

    def test_grouping_rules(self):
        self.assertIsNone(dc.grouping_problem("1,00,000"))
        self.assertIsNotNone(dc.grouping_problem("100,000"))
        self.assertIsNotNone(dc.grouping_problem("15000"))

    def test_a_comma_after_a_number_is_punctuation(self):
        nums = dc.extract_numbers("Aapka hissa ₹1,50,000, company ka ₹50,000.")
        self.assertEqual([n["canon"] for n in nums], ["₹150000", "₹50000"])
        self.assertEqual([dc.grouping_problem(n["digits"]) for n in nums], [None, None])

    def test_form_names_are_names_not_amounts(self):
        text = "Forms 19 aur 10C bharo, ₹50,000 tak. FORM 15G/15H bhi."
        self.assertEqual([n["canon"] for n in dc.extract_numbers(text)], ["₹50000"])
        self.assertEqual(dc.form_names(text), ["19", "10C", "15G", "15H"])
        self.assertEqual(dc.form_numbers("Form 10D aur Form 31"), {10, 31})

    def test_ocr_match_tolerates_symbols_but_not_wrong_digits(self):
        ocr = ["尺15.000", "SABSE COMM0N SAWAAI", "AD BUDGET . 30 DIN"]
        res = {m["text"]: m["result"] for m in verify_media.match_strings(["₹15,000", "SABSE COMMON SAWAAL", "AD BUDGET · 30 DIN"], ocr)}
        self.assertEqual(res, {"₹15,000": "pass", "SABSE COMMON SAWAAL": "pass", "AD BUDGET · 30 DIN": "pass"})
        wrong = verify_media.match_strings(["₹15,000"], ["₹15,600"])
        self.assertEqual(wrong[0]["result"], "fail")

    def test_full_width_letters_from_ocr_count_as_plain_ones(self):
        # what RapidOCR read from the S04 card: two of the letters came back full-width
        read = [verify_media.clean("AＴKＡ"), "HUA PF", verify_media.clean("₹２,00,000")]
        self.assertEqual(read, ["ATKA", "HUA PF", "₹2,00,000"])
        res = {m["text"]: m["result"] for m in verify_media.match_strings(["ATKA HUA PF", "₹2,00,000"], read)}
        self.assertEqual(res, {"ATKA HUA PF": "pass", "₹2,00,000": "pass"})

    def test_symbol_only_text_is_left_for_a_person(self):
        self.assertEqual(verify_media.match_strings(["→"], ["anything"])[0]["result"], "eye")

    def test_numbers_read_as_one_run_are_left_for_a_person(self):
        # What RapidOCR read from a correct keyframe: the ÷ and the commas were dropped
        expected = ["COST PER ENQUIRY", "≈ ₹500", "₹15,000 ÷ 30", "AGAR!"]
        ocr = ["COST PER ENQUIRY", "买500", "AGAR!", "1500030"]
        res = {m["text"]: m["result"] for m in verify_media.match_strings(expected, ocr)}
        self.assertEqual(res, {"COST PER ENQUIRY": "pass", "≈ ₹500": "pass", "₹15,000 ÷ 30": "eye", "AGAR!": "pass"})
        self.assertEqual(verify_media.unexpected_numbers(expected, ocr), [])
        # a wrong digit inside the run still fails
        bad = {m["text"]: m["result"] for m in verify_media.match_strings(expected, ["1500080"])}
        self.assertEqual(bad["₹15,000 ÷ 30"], "fail")


class TestVoiceCheck(unittest.TestCase):
    """The voice check reads numbers out of what Whisper heard, in digits, Hindi or Hinglish words."""

    def test_spoken_numbers(self):
        n = verify_voice.spoken_numbers
        self.assertEqual(n("पाँच सौ रुपये रोज़। तीस दिन। पंद्रह हज़ार का ऐड।"), [500, 30, 15000])
        self.assertEqual(n("एक हजार वियूस का एक सौ पचास रुपय पंदरा हजार में एक लाक वियूस"), [1000, 150, 15000, 100000])
        self.assertEqual(n("15 ,000 पे 18 % CTR"), [15000, 18])
        self.assertEqual(n("Ad se pehle, ek offer, ek audience, paanch minute reply."), [1, 1, 5])

    def test_twenty_five_hundred_is_not_fifty_hundred(self):
        # what a voice once said: "pachaas sau" (5,000) instead of "pachchees sau" (2,500)
        self.assertEqual(verify_voice.spoken_numbers("यानि पचास सौ का कुस्टमर"), [5000])
        self.assertEqual(verify_voice.spoken_numbers("यानी पच्चीस सौ का कस्टमर"), [2500])
        self.assertNotIn(9, verify_voice.spoken_numbers("3 % ने WhatsApp किया"))   # ने is not नौ

    def test_whisper_spellings_of_hundred_count_only_after_a_number(self):
        n = verify_voice.spoken_numbers
        self.assertEqual(n("yaani pachis saw ka customer"), [2500])     # how Whisper wrote pachchees sau
        self.assertEqual(n("यानि पच्यिस सो का कस्टमर"), [2500])
        self.assertEqual(n("एक सौप पचास रुपै"), [150])
        self.assertEqual(n("so the ad works"), [])                      # a bare "so" is not a number
        self.assertEqual(n("यानि पचास सौ का कुस्टमर"), [5000])           # and the real mistake still shows

    def test_line_numbers_and_brand(self):
        vo = "Maan lo, paanch saal ki naukri. Aur PF mein ₹2,500 ka interest."
        self.assertEqual(verify_voice.expected_numbers(vo), [2500])
        self.assertEqual(verify_voice.word_numbers(vo), {5})
        heard = verify_voice.brand_heard
        self.assertTrue(heard("PF Guru Ji", "ये है पीएफ गुरू जी।", ""))           # long ū, as Whisper often writes it
        self.assertTrue(heard("PF Guru Ji", "ये है पी एफ गुरुजी", ""))            # however Whisper splits the words
        self.assertTrue(heard("PF Guru Ji", "", "This is PF Guru Ji."))
        self.assertFalse(heard("PF Guru Ji", "ये है पीएफ कुरु जी", "This is PF Kuru Ji."))
        self.assertFalse(heard("PF Guru Ji", "ये है पीएफ गुरू", "This is PF Guru."))   # the Ji is missing
        self.assertFalse(heard("PF Guru Ji", "ये है पीएफ गर्व जी", ""))           # a near word isn't the brand
        self.assertTrue(heard("PF Guru Ji", "फॉलो करो, P.F. गुरूजी", ""))
        # the PF inside EPFO isn't the brand's PF
        self.assertFalse(heard("PF Guru Ji", "T.F. सम्झो, EPFO की हर जानकारी चाहिये, Follow करो Guru Ji.", ""))
        self.assertFalse(heard("PF Guru Ji", "Follow करो PFO Guru Ji.", ""))
        self.assertFalse(heard("PF Guru Ji", "फॉलो करो, ईपीएफ गुरु जी", ""))

    def test_whisper_spellings_of_amounts(self):
        n = verify_voice.spoken_numbers
        # what Whisper heard in ep01's S03 and S04, both said right: डेढ़ written as डेड, and a digit before लाख
        self.assertEqual(n("मान लो पास बॉक में आपका हिस्सा डेड लाक रुपये कंपनी का पचास हजार।"), [150000, 50000])
        self.assertEqual(n("कुल 2 लाक रुपाये अटके और क्लेम सीथा वापस आ गया"), [200000])
        self.assertEqual(n("your share in the passbook is Rs. 1.5 lakh, the company's Rs. 50,000."), [150000, 50000])
        self.assertEqual(n("2 लाख।"), [200000])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is needed to read the voice files")
    def test_a_voice_file_made_for_an_older_line_must_be_made_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / PILOT.name
            (ep / "media" / "audio" / "lines").mkdir(parents=True)
            (ep / "checks").mkdir()
            shutil.copy(PILOT / "episode.json", ep / "episode.json")
            f = shutil.copy(PILOT / "media" / "audio" / "lines" / "S15.mp3", ep / "media" / "audio" / "lines")
            line = next(l for l in dc.load_json(ep / "episode.json")["script"] if l["shot"] == "S15")
            key = hashlib.sha256(Path(f).read_bytes()).hexdigest()[:20]
            cache = ep / "checks" / "voice-heard.json"

            def problems(made_for):
                # what Whisper heard is in the cache, so this needs no Whisper
                entry = {"file": "S15.mp3", "hi": line["tts"], "tts": made_for}
                cache.write_text(json.dumps({key: entry}, ensure_ascii=False), encoding="utf-8")
                return " ".join(verify_voice.check_lines(ep, only={"S15"}, cache_path=cache)[0]["problems"])
            self.assertIn("older version", problems("पीएफ समझो, क्लेम पाओ। ये है पुराना ब्रांड।"))
            self.assertNotIn("older version", problems(line["tts"]))
            self.assertNotIn("older version", problems(line["tts"].replace("।", "").replace(",", " ")))  # only punctuation
            # a file checked for the first time: its text is noted, so a later change to the line is caught
            cache.write_text(json.dumps({key: {"file": "S15.mp3", "hi": line["tts"]}}, ensure_ascii=False), encoding="utf-8")
            res = verify_voice.check_lines(ep, only={"S15"}, cache_path=cache)[0]
            self.assertNotIn("older version", " ".join(res["problems"]))
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8"))[key]["tts"], line["tts"])

    def test_rates_and_fractions_are_heard_as_decimals(self):
        n = verify_voice.spoken_numbers
        self.assertEqual(n("आठ पॉइंट दो पाँच परसेंट"), [8.25])          # how an interest rate is said
        self.assertEqual(n("सात दशमलव एक प्रतिशत"), [7.1])
        self.assertEqual(n("8.25 प्रतिशत"), [8.25])                     # how Whisper may write it
        self.assertEqual(n("8 पॉइंट 25 परसेंट"), [8.25])
        self.assertEqual(n("सवा आठ प्रतिशत"), [8.25])
        self.assertEqual(n("साढ़े सात हज़ार"), [7500])
        self.assertEqual(n("पौने दो लाख"), [175000])
        self.assertEqual(n("दो पॉइंट शून्य पाँच"), [2.05])
        self.assertEqual(verify_voice.expected_numbers("Aur EPF? Poore 8.25%! ₹8,250."), [8.25, 8250])

    def test_numbers_said_in_english_are_heard(self):
        n = verify_voice.spoken_numbers
        self.assertEqual(n("एट पॉइंट टू फ़ाइव परसेंट"), [8.25])                 # how the voice text writes 8.25%
        self.assertEqual(n("वन लाख रुपीज़"), [100000])
        self.assertEqual(n("एट थाउज़ेंड टू हंड्रेड फ़िफ़्टी"), [8250])
        self.assertEqual(n("ट्वेंटी फ़ाइव"), [25])                              # tens and ones make one number
        self.assertEqual(n("ट्वेल्व महीने, ट्वेंटी दिन"), [12, 20])
        self.assertEqual(n("eight point two five percent, one lakh"), [8.25, 100000])   # how Whisper may write it
        self.assertEqual(n("फ़ॉर्म थर्टी वन"), [31])
        self.assertEqual(n("प्रोसीड फ़ॉर ऑनलाइन क्लेम"), [])                   # "for" is a word, not four
        self.assertEqual(n("दो तीन"), [2, 3])                                    # Hindi number words stay apart
        self.assertEqual(n("सिक्स्टी दिन बाद"), [60])                            # sixty, spelled for a crisper t

    def test_the_voice_maker_gives_each_quote_to_its_speaker(self):
        import make_voice
        line = {"tts": '"पुराना यू ए एन है?" शिवम बोला: "नया बना दो ना!"', "speakers": ["priya", "narrator"]}
        self.assertEqual(make_voice.parts_of(line), [("priya", "पुराना यू ए एन है?"),
                                                     ("narrator", "शिवम बोला: नया बना दो ना!")])   # read together
        self.assertEqual(make_voice.parts_of({"tts": 'प्रिया ने कहा: "हाँ।"'}),
                         [("narrator", "प्रिया ने कहा: हाँ।")])                  # no speakers: the narrator reads it
        for who in ("narrator", "shivam", "priya", "ravi", "papa"):
            self.assertIn(who, make_voice.VOICES)
            self.assertTrue((make_voice.VOICE_DIR / (make_voice.VOICES[who] + ".wav")).exists())
            self.assertTrue((make_voice.VOICE_DIR / (make_voice.VOICES[who] + ".txt")).read_text(encoding="utf-8").strip())

    def test_the_voice_maker_knows_which_initialisms_a_line_spells(self):
        import make_voice
        self.assertEqual(make_voice.initialisms("नया यू ए एन, मतलब पुराना पी एफ़, पुराने यू ए एन में अटका।"),
                         ["uan", "pf", "uan"])
        self.assertEqual(make_voice.initialisms("ईपीएफ़ओ की हर जानकारी, पी एफ़ गुरु जी"), ["epfo", "pf"])  # not जी
        self.assertEqual(make_voice.initialisms("फिर मेंबर पोर्टल पे केवाईसी: आधार, बैंक और पैन।"), ["kyc"])
        self.assertEqual(make_voice.initialisms("दोस्त के लिए"), [])                       # के alone is a word
        count = make_voice.initialism_count
        self.assertEqual(count("uan", "नया UAN, U.A.N. और यू ए एन"), 3)
        self.assertEqual(count("pf", "T.F. Sampao EPFO की"), 0)                   # EPFO has PF's letters, not PF
        self.assertEqual(count("pf", "पीफ समझो"), 0)                               # "peef" isn't P-F

    def test_the_voice_maker_keeps_the_take_that_says_the_whole_part(self):
        import make_voice
        judge = make_voice.judge
        vo = "Naukri badlo, company badlo, UAN wahi rehta hai."
        text = "नौकरी बदलो, कंपनी बदलो, यू ए एन वही रहता है।"
        self.assertEqual(judge(text, "नौकरी बदलो, कंपनी बदलो, UAN वही रहता है।", vo), ([], 0, 0))
        self.assertEqual(judge(text, "COMPANY BADLO, UAN वही रहता है।", vo), ([], 2, 0))   # the first words swallowed
        self.assertEqual(judge(text, "कंपनी बद्लो, यू एन वही रहता है।", vo)[0], ["initialism UAN"])
        vo = "PF samjho, claim pao. EPFO ki har jankari chahiye? Follow karo PF Guru Ji."
        text = "पी एफ़ समझो, क्लेम पाओ। ईपीएफ़ओ की हर जानकारी चाहिए? फ़ॉलो करो, पी एफ़ गुरु जी।"
        self.assertEqual(judge(text, "O PF समझो, Claim पाओ, EPFO की हर जानकारी चाहिये, Follow करो, PF Guru Ji", vo),
                         ([], 0, 1))                                                     # a stray sound before it
        self.assertEqual(judge(text, "T.F. Sampao EPFO की हर जानकारी चाहिये. Follow करो P.F. Guru Ji.", vo)[0],
                         ["initialism PF"])
        self.assertEqual(judge("यू ए एन एक ही होता है।", "UAN 1 ही होता है", ""), ([], 0, 0))   # एक written as 1
        vo = "Shivam ki nayi naukri! Pehla din, aur HR ka pehla sawaal."
        text = "शिवम की नई नौकरी! पहला दिन, और एचआर का पहला सवाल।"
        # Whisper writes नई as नहीं even from a native speaker, and नौकरी as it's said, नौक्री
        self.assertEqual(judge(text, "शिवम की नहीं नौक्री पहला दिन और HR का पहला सवाल", vo), ([], 0, 0))
        self.assertEqual(judge(text, "नहीं नौक्री पहला दिन और H.R. का पहला सवाल", vo), ([], 2, 0))
        self.assertEqual(judge("नहीं डाली? सिक्सटी दिन बाद शिवम खुद मार्क एग्ज़िट कर सकता है।",
                               "नहीं डाली। 20 दिन बाद शिवम खुद मार्क एग्सिट कर सकता है।", "")[0], ["number 60"])
        vo = '"Purana UAN hai?" Shivam bola: "Naya bana do na!"'
        self.assertEqual(judge("पुराना यू ए एन है?", "उहाँ पुराना UAN है।", vo), ([], 0, 1))   # the lead left on
        self.assertEqual(judge("शिवम बोला: नया बना दो ना!", "शिवम बोला नया बना दोना", vo), ([], 0, 0))
        self.assertEqual(judge("रास्ता सीधा है।", "त्रास्ता सीधा है।", ""), ([], 1, 1))     # a sound before the word
        self.assertEqual(judge("फिर मेंबर पोर्टल।", "अफिर मेंबर पोर्टल।", ""), ([], 1, 1))
        self.assertEqual(judge("नाम और जन्म तिथि बिलकुल आधार जैसे। गलत हो, तो खुद ठीक करो।",
                               "नाम और जन्मतिथी बिल्कुल आदार जैसे गलत हो, तो खुद थीक करो।", ""), ([], 0, 0))

    def test_the_voice_maker_says_an_initialism_as_one_word(self):
        import numpy as np
        import make_voice
        sr = make_voice.SR
        t = np.arange(int(0.15 * sr)) / sr
        letter = (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
        gap = np.zeros(int(0.15 * sr), np.float32)
        take = np.concatenate([letter, letter, letter, gap, letter, gap, letter, gap, letter])   # पुराना यू·ए·एन, है
        W = make_voice.Word
        words = [W(0.0, 0.3, "पुराना"), W(0.3, 1.05, "UAN"), W(1.2, 1.35, "है")]
        spans = make_voice.initialism_spans(words, ["uan"])
        self.assertEqual(spans, [("uan", 0.3, 1.05)])
        gaps = make_voice.letter_gaps(take, spans)
        self.assertEqual(len(gaps), 2)                                     # between the letters, not after UAN
        tight = make_voice.close_gaps(take, gaps)
        self.assertAlmostEqual((len(take) - len(tight)) / sr, 2 * (0.15 - make_voice.LETTER_GAP), delta=0.03)
        self.assertEqual(make_voice.initialism_spans([W(0, 0.2, "EPFO")], ["pf"]), [])   # PF isn't in EPFO
        t = np.arange(int(0.8 * sr)) / sr
        uan = (0.3 * np.sin(2 * np.pi * 150 * t)).astype(np.float32)          # UAN said slowly, in 0.8 s
        line = np.concatenate([gap, uan, gap])
        self.assertEqual(make_voice.Voice.slow([("uan", 0.15, 0.95)]), 1)
        quick = make_voice.quicken(line, [("uan", 0.15, 0.95)])
        said = (len(quick) - 2 * len(gap)) / sr
        self.assertAlmostEqual(said, 0.8 / make_voice.MAX_QUICK, delta=0.04)   # sped up as far as allowed
        spectrum = np.abs(np.fft.rfft(quick[len(gap):len(gap) + 4096] * np.hanning(4096)))
        self.assertAlmostEqual(np.fft.rfftfreq(4096, 1 / sr)[np.argmax(spectrum)], 150, delta=8)   # same pitch

    def test_the_voice_maker_cuts_off_the_lead_word(self):
        import numpy as np
        import make_voice
        sr = make_voice.SR
        t = np.arange(int(0.3 * sr)) / sr
        word = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        gap = np.zeros(int(0.25 * sr), np.float32)
        take = np.concatenate([gap[:2400], word, gap, word, word])        # हाँ, a pause, then the part
        self.assertTrue(all(make_voice.is_lead(w) for w in ("हाँ।", "हां,", "उहाँ", "Haan.")))
        self.assertFalse(any(make_voice.is_lead(w) for w in ("हैं", "नया", "हाथ")))
        cut = make_voice.cut_lead(take, [])                                # Whisper didn't write the lead
        self.assertAlmostEqual(len(cut) / sr, 0.6 + 0.125, delta=0.03)     # cut in the middle of the pause
        long_first = np.concatenate([gap[:2400], word, word, word, gap, word])   # a long first sound isn't the lead
        self.assertEqual(len(make_voice.cut_lead(long_first, [])), len(long_first))

    def test_a_rate_whisper_half_wrote_in_digits_is_still_heard(self):
        n = verify_voice.spoken_numbers
        # how Whisper heard ep04's S10 in the Bunty voice: "two" as टॉ, "five percent" as 5%
        self.assertEqual(n("बस याद रखो, रेट हर साल ताया होता है, एट पॉइंट टॉ 5% पिछले साल का है।"), [8.25])
        self.assertEqual(n("एट पॉइंट टो फ़ाइव परसेंट"), [8.25])
        self.assertEqual(n("एट पॉइंट 25 परसेंट"), [8.25])
        self.assertEqual(n("5 लोग, एट पॉइंट टू 5%"), [5, 8.25])
        self.assertEqual(n("एट पॉइंट टू, 5 साल"), [5, 8.2])                     # not across a comma
        self.assertEqual(n("टॉ"), [])                                            # only after the point

    def test_voice_script_is_devanagari_without_digits(self):
        for line in dc.load_json(PILOT / "episode.json")["script"]:
            self.assertRegex(line["tts"], r"[ऀ-ॿ]", line["shot"])
            self.assertNotRegex(line["tts"], r"[0-9०-९]", line["shot"])
            self.assertNotRegex(line["tts"], r"[A-Za-z]", line["shot"])


class TestScriptReview(EpisodeCase):
    """From brand.json → rules → script_review_from on, a person reads and approves a reel's script and hook before
    anything else is made. These tests treat the pilot as such a reel."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(script_review, "first_reviewed", return_value=1)
        p.start()
        self.addCleanup(p.stop)

    def approve(self, **over):
        rec = {"version": script_review.version(self.ep), "approved_by": dc.brand()["approvers"][0],
               "approved_on": "2026-11-16", "their_words": "script OK"}
        rec.update(over)
        dc.save_json(self.ep_dir / script_review.APPROVAL, rec)
        return rec

    def report(self):
        return check_episode.check(self.ep_dir, use_voice=False, use_ocr=False)

    def review_items(self, rep):
        return [p for p in rep.person + rep.fix if p["area"] == "Script review"]

    def test_the_version_follows_the_words_not_the_voice_spelling(self):
        v = script_review.version(self.ep)
        self.assertRegex(v, r"^[0-9a-f]{6}$")
        line = self.line("S03")
        line["tts"] = line["tts"].replace("।", "! ", 1)                  # respelled for the voice
        line["delivery"] = "warm · a new cue"                           # said another way
        line["vo"] = " " + line["vo"].replace(" ", "  ", 1) + " "        # spaced differently
        self.ep["hook_options"] = ["Claim reject? Pehle yeh dekho."]   # options aren't in the reel
        self.assertEqual(script_review.version(self.ep), v)
        line["vo"] += "!"
        self.assertNotEqual(script_review.version(self.ep), v)
        line["vo"] = line["vo"][:-1]
        self.assertEqual(script_review.version(self.ep), v)              # back to the approved words
        self.ep["post"]["cover"]["stamp"] = "NAYA STAMP"
        self.assertNotEqual(script_review.version(self.ep), v)          # the cover is a hook too

    def test_until_a_person_approves_nothing_after_the_script_is_checked(self):
        rep, text = self.report()
        self.assertEqual(rep.result(), "WAITING", text)
        item, = self.review_items(rep)
        self.assertIn(item, rep.person)                                  # a person's part, not Muse's
        self.assertIn(script_review.version(self.ep), item["what"])
        self.assertIn("script.md", item["how"])
        self.assertIn("script-approved.json", item["how"])
        self.assertIn("everything after the script waits for its review", text)
        self.assertNotIn("Reel file:", text)                             # reel.json isn't checked yet
        self.assertIn("already made: shots, reel.json", text)
        self.assertNotIn("03-script", text)                              # the review is the script's approval

    def test_an_approval_of_this_version_lets_the_rest_be_checked(self):
        rec = self.approve()
        st = script_review.status(self.ep_dir)
        self.assertEqual((st["state"], st["cleared"]), ("approved", True))
        rep, text = self.report()
        self.assertEqual(self.review_items(rep), [])
        self.assertIn("Script review: {} approved version {} on 2026-11-16".format(rec["approved_by"], rec["version"]), text)
        self.assertIn("Reel file:", text)
        self.approve(version="Version `{}`".format(rec["version"].upper()))     # however Muse copied the code
        self.assertEqual(script_review.status(self.ep_dir)["state"], "approved")

    def test_respelling_a_voice_line_keeps_the_approval(self):
        self.approve()
        self.line("S03")["tts"] = self.line("S03")["tts"].replace("।", "!", 1)
        self.line("S03")["delivery"] = "concerned · a new cue"
        self.save()
        self.assertEqual(script_review.status(self.ep_dir)["state"], "approved")

    def test_a_changed_script_goes_back_to_the_person(self):
        old = self.approve()["version"]
        self.line("S03")["vo"] += "!"
        self.save()
        st = script_review.status(self.ep_dir)
        self.assertEqual((st["state"], st["cleared"]), ("changed", False))
        rep, text = self.report()
        item, = self.review_items(rep)
        self.assertIn(item, rep.person)
        self.assertIn("changed after {} approved version {}".format(dc.brand()["approvers"][0], old), item["what"])
        self.assertIn(st["version"], item["what"])
        self.assertNotIn("Reel file:", text)

    def test_only_a_listed_person_approves(self):
        self.approve(approved_by="Muse")
        rep, text = self.report()
        self.assertEqual(rep.result(), "FIX", text)
        item, = self.review_items(rep)
        self.assertIn(item, rep.fix)
        self.assertIn("approved_by is 'Muse'", item["what"])
        self.approve(approved_by="Someone Else")
        self.assertEqual(script_review.status(self.ep_dir)["state"], "not an approver")
        rep, _ = self.report()
        item, = self.review_items(rep)
        self.assertIn(item, rep.person)
        self.assertIn("approvers", item["what"])
        self.approve(approved_on="16/11/2026", their_words="", version="abc")
        st = script_review.status(self.ep_dir)
        self.assertEqual(st["state"], "wrong file")
        self.assertEqual(len(st["problems"]), 3, st["problems"])
        (self.ep_dir / script_review.APPROVAL).write_text("{not json", encoding="utf-8")
        self.assertEqual(script_review.status(self.ep_dir)["state"], "wrong file")

    def test_the_script_page(self):
        v = script_review.version(self.ep)
        self.ep["hook_options"] = ["Claim reject? Pehle yeh dekho.", "Aapka claim kyun ruka?"]
        self.save()
        self.assertIn("script.md", new_episode.prepare(self.ep_dir))
        page = (self.ep_dir / "script.md").read_text(encoding="utf-8")
        self.assertIn("**Version `{}`**".format(v), page)
        self.assertIn("**Waiting for your review.**", page)
        self.assertIn("- **Hook A** · Claim reject? Pehle yeh dekho.", page)
        self.assertIn("**{}**".format(self.line("S01")["vo"]), page)
        for line in self.ep["script"]:
            self.assertIn("| {} | {} | {} |".format(line["shot"], line["chapter"], script_review._cell(line["vo"])), page)
        self.assertIn("The cover says **CLAIM / REJECT?**, with the stamp **WAJAH + FIX**.", page)
        for d in self.ep["data"]:
            if d["kind"] == "rule":                                       # every rule, with its source
                self.assertIn(script_review._cell(d["label"]), page)
        self.assertIn("**not checked yet**", page)                        # the test pilot's facts are unchecked
        self.assertIn('write "script OK"', page)
        self.assertIn("Hook A", page.split("## How to reply")[1])
        self.approve()
        self.assertIn("script.md", new_episode.prepare(self.ep_dir))      # the page says it's approved
        page = (self.ep_dir / "script.md").read_text(encoding="utf-8")
        self.assertIn("**Approved** by {} on 2026-11-16 (\"script OK\")".format(dc.brand()["approvers"][0]), page)
        self.assertNotIn("script.md", new_episode.prepare(self.ep_dir))   # and isn't rewritten when nothing changed

    def test_old_and_posted_reels_need_no_review(self):
        with mock.patch.object(script_review, "first_reviewed", return_value=5):
            st = script_review.status(self.ep_dir)
            self.assertEqual((st["state"], st["cleared"]), ("not needed", True))
            self.assertFalse(script_review.write(self.ep_dir))
            _, text = self.report()
            self.assertNotIn("Script review", text)
        dc.save_json(self.ep_dir / "posted.json", {"url": "https://www.instagram.com/reel/x/", "posted_on": "2026-11-20",
                                                   "post_it_from": dc.brand()["approvers"][0]})
        st = script_review.status(self.ep_dir)
        self.assertEqual((st["state"], st["cleared"]), ("posted", True))

    def test_the_other_hooks_use_numbers_from_data(self):
        self.ep["hook_options"] = ["Sirf ₹99 mein claim?", "Claim reject ho gaya?"]
        self.save()
        msgs = [i["msg"] for i in self.run_checks().of("fail") if i["id"] == "E3.15"]
        self.assertEqual(msgs, ["hook option A says ₹99, which isn't a value in data"])
        self.ep["hook_options"] = "Claim reject ho gaya?"
        self.save()
        self.assertIn("E3.15", self.fail_ids(self.run_checks()))

    def test_approve_records_the_version_the_person_read(self):
        import approve
        a = argparse.Namespace(episode=str(self.ep_dir), version="0000ff", by=dc.brand()["approvers"][0], words="script OK")
        with self.assertRaises(SystemExit):                               # a page that isn't this script
            approve.cmd_script(a)
        self.assertFalse((self.ep_dir / script_review.APPROVAL).exists())
        a.version = script_review.version(self.ep)
        approve.cmd_script(a)
        self.assertEqual(script_review.status(self.ep_dir)["state"], "approved")
        a.by = "Muse"
        with self.assertRaises(SystemExit):                               # never an AI
            approve.cmd_script(a)

    def test_github_builds_only_an_approved_script(self):
        ep5 = self.tmp / "ep05-claim-reject"                              # the real rule: ep05 on
        shutil.copytree(self.ep_dir, ep5)

        def cleared(ep_dir):
            return subprocess.run([sys.executable, str(ROOT / "tools" / "script_review.py"), str(ep_dir), "--cleared"],
                                  capture_output=True, text=True)
        r = cleared(ep5)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("waiting for a person to approve version", r.stdout)
        ep = dc.load_json(ep5 / "episode.json")
        dc.save_json(ep5 / script_review.APPROVAL, {"version": script_review.version(ep), "approved_by": dc.brand()["approvers"][0],
                                                    "approved_on": "2026-11-16", "their_words": "script OK"})
        r = cleared(ep5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        flow = (ROOT / ".github" / "workflows" / "build-reel.yml").read_text(encoding="utf-8")
        self.assertIn('python3 tools/script_review.py "$ep" --cleared', flow)
        self.assertIn('"episodes/*/script-approved.json"', flow)
        self.assertIn("\n          git add episodes/*/script.md 2>/dev/null || true\n", flow)   # on its own line


class TestScriptReviewStartsAtEp05(unittest.TestCase):
    def test_the_reels_made_before_it_need_no_review(self):
        self.assertEqual(script_review.first_reviewed(), 5)
        for ep_dir in dc.episode_dirs():
            if script_review.number(ep_dir) < 5:
                st = script_review.status(ep_dir)
                self.assertTrue(st["cleared"], (ep_dir.name, st["state"]))
                self.assertFalse((ep_dir / "script.md").exists(), ep_dir.name)


class TestCutouts(unittest.TestCase):
    """PF Stories: people and things cut from paper (tools/cutout.py), and how the reel moves them."""
    DEMO = ROOT / "brand" / "assets" / "style-frames" / "cutout-demo"

    @classmethod
    def setUpClass(cls):
        import cutout
        cls.cutout = cutout
        cls.paper = build_reel.Paper()

    def test_every_person_in_every_pose(self):
        c = self.cutout
        for who in c.CAST:
            for pose in c.POSES:
                img, (gx, gy) = c.person(who, pose, "smile", phase=0.8 if pose == "walk" else None)
                self.assertEqual(img.mode, "RGBA")
                box = img.getchannel("A").getbbox()
                self.assertIsNotNone(box, (who, pose))
                self.assertGreater(box[0], 0, (who, pose))                       # nothing cut off the canvas
                self.assertLess(box[2], img.width, (who, pose))
                self.assertGreater(box[1], 0, (who, pose))
                self.assertLessEqual(abs(box[3] - gy), 12, (who, pose))          # it stands on its ground point
        for mood in c.MOODS:
            c.person("shivam", "stand", mood)
        a, _ = c.person("priya", "wave", "happy", wave=0.4)
        b, _ = c.person("priya", "wave", "happy", wave=0.4)
        self.assertEqual(a.tobytes(), b.tobytes())                               # the same pose is the same image
        with self.assertRaises(KeyError):
            c.person("nobody")

    def test_a_hand_reaches_its_target_with_the_arm_its_own_length(self):
        c = self.cutout
        for target in ((60, -560), (20, -470), (250, -430), (-30, -650)):
            sho = (c.SHOULDER_X, c.SHOULDER_Y + 8)
            el, wr = c._ik(sho, target, c.UPPER_ARM, c.FOREARM, 1)
            self.assertAlmostEqual(math.dist(sho, el), c.UPPER_ARM, delta=0.5)
            self.assertAlmostEqual(math.dist(el, wr), c.FOREARM, delta=0.5)

    def test_every_prop_and_the_white_cut_edge(self):
        c = self.cutout
        for kind in c.PROPS:
            img, anchors = c.prop(kind)
            self.assertIsNotNone(img.getchannel("A").getbbox(), kind)
            done = c.finish(img, self.paper, 3)
            self.assertEqual(done.size, (img.width + 2 * c.PAD, img.height + 2 * c.PAD))
        tick, _ = c.prop("tick")
        done = c.finish(tick, self.paper, 3)
        x0, y0, x1, y1 = tick.getchannel("A").getbbox()
        r, g, b, a = done.getpixel((x0 + c.PAD - 3, (y0 + y1) // 2 + c.PAD))  # just outside the shape: white paper
        self.assertGreater(a, 200)
        self.assertGreater(min(r, g, b), 225)
        with self.assertRaises(KeyError):
            c.prop("rocket")

    def test_the_demo_draws_only_its_card_text(self):
        reel = build_reel.Reel(self.DEMO, use_voice=False)
        self.assertEqual(reel.check_texts(), [])
        spec = json.loads((self.DEMO / "reel.json").read_text(encoding="utf-8"))
        spec["shots"]["S03"].append({"type": "bubble", "text": "NAYA UAN BANA DO", "x": 300, "y": 500})
        spec["shots"]["S04"][1]["label"] = "EPFO HQ"
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "cutout-demo"
            shutil.copytree(self.DEMO, ep)
            (ep / "reel.json").write_text(json.dumps(spec), encoding="utf-8")
            problems = build_reel.Reel(ep, use_voice=False).check_texts()
        self.assertIn('S03 draws "NAYA UAN BANA DO", which isn\'t in its card_text', problems)
        self.assertIn('S04 draws "EPFO HQ", which isn\'t in its card_text', problems)

    def test_unknown_names_stop_the_build(self):
        ctx = {"paper": self.paper, "photos": {}, "screens": {}, "seed": 1}
        with self.assertRaises(KeyError):
            build_reel.Puppet({"who": "nobody"}, ctx)
        with self.assertRaises(SystemExit):
            build_reel.Puppet({"who": "shivam", "moves": [{"do": "pose", "pose": "dance"}]}, ctx)
        with self.assertRaises(SystemExit):
            build_reel.Prop({"kind": "rocket"}, ctx)

    def test_moves_land_on_their_words_and_walks_take_their_time(self):
        reel = build_reel.Reel(self.DEMO, use_voice=False)
        s1 = reel.elements[0]
        shivam = next(e for e in s1 if isinstance(e, build_reel.Puppet))
        jump = next(m for m in shivam.moves if m["do"] == "jump")
        shot = reel.E.shots[0]
        word_at = reel.E.word_time(shot, "pehli")
        self.assertAlmostEqual(shivam.at + jump["at"], word_at - 0.12, places=2)   # on the word, a beat early
        (t0, t1, a, b), = shivam.walks
        self.assertEqual((a, b), (-140, 330))
        mid = (t0 + t1) / 2
        x, _, key = shivam.look(*build_reel.stop_motion(mid))
        self.assertTrue(a < x < b)
        self.assertEqual(key[0], "walk")
        self.assertEqual(key[-1], 1)                                             # facing the way it walks
        self.assertGreaterEqual(reel.E.min_length("S01"), shivam.at + t1)        # the shot lasts the whole walk

    def test_stop_motion_holds_each_pose_for_a_twelfth_of_a_second(self):
        reel = build_reel.Reel(self.DEMO, use_voice=False)
        shivam = next(e for e in reel.elements[0] if isinstance(e, build_reel.Puppet))
        u = 0.7
        k = build_reel.stop_motion(u)[1]
        a = shivam.frame_image(k / 12 + 0.001)
        b = shivam.frame_image(k / 12 + 0.07)                                    # the same pose
        self.assertIs(a, b)
        self.assertEqual(shivam.state(k / 12 + 0.001), shivam.state(k / 12 + 0.07))
        c = shivam.frame_image((k + 1) / 12 + 0.001)                             # the next pose
        self.assertIsNot(a, c)
        frame = reel.render(0.9)
        self.assertEqual(frame.size, (build_reel.W, build_reel.H))


class TestHandwriting(unittest.TestCase):
    def test_unread_handwriting_is_left_for_an_eye_but_never_a_number(self):
        def run(expected, lines, hand):
            res = verify_media.Result("t")
            verify_media.text_check(res, expected, lines, "S15", handwritten=hand)
            return res.failed
        self.assertFalse(run(["us dost ko"], ["SHARE"], ["us dost ko"]))     # handwriting OCR missed: eye
        self.assertTrue(run(["us dost ko"], ["SHARE"], []))                  # printed text missed: fail
        self.assertTrue(run(["18% CTR"], ["CTR"], ["18% CTR"]))             # a number must still be read


class TestOcrRobustness(unittest.TestCase):
    def test_words_in_any_order_pass_but_wrong_words_fail(self):
        # a tilted, letter-spaced tab comes back from OCR in pieces, sorted by height
        exp = ["AAPKA BUDGET · 30 DIN"]
        self.assertEqual(verify_media.match_strings(exp, ["BUDGET", "AAPKA", "30 DIN"])[0]["result"], "pass")
        self.assertEqual(verify_media.match_strings(exp, ["BUDGET", "TUMHARA", "30 DIN"])[0]["result"], "fail")

    def test_a_lone_digit_is_left_for_a_person_but_a_different_digit_fails(self):
        self.assertEqual(verify_media.match_strings(["DIN 3"], ["DIN"])[0]["result"], "eye")
        self.assertEqual(verify_media.match_strings(["DIN 3"], ["DIN 8"])[0]["result"], "fail")
        self.assertEqual(verify_media.match_strings(["₹15,000"], ["₹15,800"])[0]["result"], "fail")


@unittest.skipUnless(build_reel, "Pillow and numpy are needed for the reel builder")
class TestReelBuilder(unittest.TestCase):
    def test_reel_may_only_draw_the_shots_card_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / PILOT.name
            shutil.copytree(PILOT, ep, ignore=shutil.ignore_patterns("media", "build", "test"))
            self.assertEqual([p for p in build_reel.Reel(ep).check_texts() if "placeholder" not in p], [])
            reel = json.loads((ep / "reel.json").read_text(encoding="utf-8"))
            reel["shots"]["S04"][0]["big"] = "₹2,10,000"
            (ep / "reel.json").write_text(json.dumps(reel, ensure_ascii=False), encoding="utf-8")
            problems = build_reel.Reel(ep).check_texts()
            self.assertTrue(any("₹2,10,000" in p and "isn't in its card_text" in p for p in problems))
            self.assertTrue(any("₹2,00,000" in p and "isn't drawn" in p for p in problems))

    def test_end_card_shows_the_logo_and_pops_the_follow_button_on_its_word(self):
        reel = build_reel.Reel(PILOT, use_voice=False)
        card = next(el for el in reel.elements[-1] if isinstance(el, build_reel.EndCard))
        note, button = dc.follow_line()
        self.assertEqual(card.texts()[1:3], [note, button])
        self.assertEqual(card.handwritten(), [card.spec["tagline"], note])    # OCR misses there go to an eye
        self.assertTrue(card.logo_file.exists())
        self.assertGreater(card.cta_at, 0.3)                                   # the button waits for "Follow"
        before, after = card.art(card.cta_at - 0.05), card.art(card.cta_at + 1)
        self.assertEqual(before.size, after.size)

        def opaque(im):
            return sum(im.getchannel("A").histogram()[128:])
        self.assertGreater(opaque(after), opaque(before) + 20000)            # the button is about 560 x 110 px
        self.assertIn(("pop", 10 + card.cta_at), card.sounds(10))

    def test_a_missing_logo_is_reported_and_the_name_is_drawn_instead(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / PILOT.name
            shutil.copytree(PILOT, ep, ignore=shutil.ignore_patterns("media", "build", "test"))
            reel = json.loads((ep / "reel.json").read_text(encoding="utf-8"))
            reel["shots"]["S15"][1]["logo_file"] = "brand/assets/logo/missing.png"
            (ep / "reel.json").write_text(json.dumps(reel, ensure_ascii=False), encoding="utf-8")
            r = build_reel.Reel(ep, use_voice=False)
            self.assertTrue(any("missing.png" in p and "is missing" in p for p in r.check_texts()))
            card = next(el for el in r.elements[-1] if isinstance(el, build_reel.EndCard))
            self.assertEqual(card.logo().width, card.W)                        # the brand name, in big letters
            self.assertEqual(r.render(r.E.length - 0.1).size, (1080, 1920))

    def test_a_frame_renders_at_full_size(self):
        img = build_reel.Reel(PILOT, use_voice=False).render(29.5)
        self.assertEqual(img.size, (1080, 1920))

    def test_without_fonttools_a_missing_character_is_still_found(self):
        # CI installs fontTools; without it (a laptop, Muse's sandbox) covered() draws the character instead
        frame = build_reel.Reel(PILOT, use_voice=False).render(29.5)
        build_reel.covered.cache_clear()
        self.addCleanup(build_reel.covered.cache_clear)
        with mock.patch.object(build_reel, "coverage", return_value=None):
            self.assertTrue(build_reel.covered("type", "5"))
            self.assertFalse(build_reel.covered("type", "₹"))          # Courier Prime has no rupee sign,
            self.assertEqual(build_reel.runs("₹500", "type"), [["₹", "mono"], ["500", "type"]])   # so Plex Mono draws it
            self.assertEqual(build_reel.Reel(PILOT, use_voice=False).render(29.5).tobytes(), frame.tobytes())


class TestMediaRules(unittest.TestCase):
    def test_near_miss_picks_the_closest_expected_number(self):
        self.assertEqual(verify_media.near_miss("15800", ["15000", "30"]), "15000")
        self.assertEqual(verify_media.near_miss("17100", ["15000", "17700"]), "17700")
        self.assertIsNone(verify_media.near_miss("00", ["30"]))
        self.assertIsNone(verify_media.near_miss("2026", ["15000"]))

    def test_the_rupee_sign_read_as_a_digit(self):
        def result(card, read):
            return ([m["result"] for m in verify_media.match_strings([card], [read])],
                    verify_media.unexpected_numbers([card], [read]))
        # ep04 S02: the tab's small ₹ came back as a 5
        self.assertEqual(result("MAAN LO · HAR ₹1,00,000 PE", "MAAN LO · HAR 5100000 PE"), (["pass"], []))
        self.assertEqual(result("₹15,000", "715000"), (["pass"], []))            # as a 7 or a 2, as before
        # without ₹ on the card, a 5 in front is a wrong number
        self.assertEqual(result("HAR 1,00,000 LOG", "HAR 5100000 LOG"), (["fail"], ["5100000"]))
        self.assertEqual(result("₹1,00,000", "5200000"), (["fail"], ["5200000"]))

    def test_code_route_prompts(self):
        saved = build_prompts.routes
        build_prompts.routes = lambda ep_dir=None: ("code", "code")
        try:
            text = build_prompts.render(PILOT)
        finally:
            build_prompts.routes = saved
        self.assertIn("## Code build rules", text)
        self.assertIn("episodes/ep01-claim-reject/build/S06.py", text)
        self.assertIn("brand/fonts/", text)
        self.assertNotIn("**Self-check**", text)
        self.assertNotIn("episodes/EP/", text)
        # every shot's exact text is still listed
        for shot in dc.load_json(PILOT / "episode.json")["shots"]:
            for t in shot.get("card_text", []):
                self.assertIn("- `{}`".format(t), text)

    def test_build_route_prompts_list_what_muse_makes(self):
        text = build_prompts.render(PILOT)          # the pilot has a reel.json
        self.assertIn("## 1 · Photos", text)
        self.assertIn("episodes/ep01-claim-reject/media/audio/lines/S01.mp3", text)
        self.assertIn("पीएफ क्लेम रिजेक्ट हो गया? पैसा अटका है?", text)
        self.assertIn("| ₹2,00,000 |", text)                     # what to listen for in S04
        self.assertNotIn("without silence", text)
        self.assertNotIn("**Self-check**", text)
        for shot in dc.load_json(PILOT / "episode.json")["shots"]:
            for t in shot.get("card_text", []):
                self.assertIn("`{}`".format(t), text)

    def test_prompts_carry_the_brand_signoff_and_follow_line(self):
        b = dc.brand()
        note, button = dc.follow_line()
        writing = build_prompts.render_writing(PILOT)
        self.assertIn('signoff: exactly "{}"'.format(b["signoff"]), writing)
        self.assertIn('"{}"'.format(note), writing)
        self.assertIn('"{}"'.format(button), writing)
        for name in ("script-writer.txt", "reel-writer.txt"):
            self.assertNotRegex(dc.prompt_text(name), r"\{\{(SIGNOFF|TAGLINE|FOLLOW_NOTE|FOLLOW_BUTTON)\}\}")
        # reel-writer.txt cues the end card on "EPFO" and its button on "Follow": the sign-off must say both
        words = {re.sub(r"[^0-9a-z]", "", w.lower()) for w in b["signoff"].split()}
        self.assertLessEqual({"epfo", "follow"}, words)

    def test_each_line_can_say_how_the_voice_says_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / PILOT.name
            shutil.copytree(PILOT, ep, ignore=shutil.ignore_patterns("media", "build"))
            self.assertIn("| Shot | Save as | Say exactly | Listen for |", build_prompts.render(ep))   # no directions, no column
            e = dc.load_json(ep / "episode.json")
            e["script"][0]["delivery"] = "curious · slow down on paisa"
            dc.save_json(ep / "episode.json", e)
            text = build_prompts.render(ep)
            self.assertIn("| Shot | Save as | Say exactly | How to say it | Listen for |", text)
            self.assertIn("| curious · slow down on paisa |", text)
        self.assertIn('"delivery"', dc.prompt_text("script-writer.txt"))
        self.assertIn("How to say it", dc.prompt_text("voice.txt"))
        # an ellipsis or an exclamation mark in the voice text isn't a new line to record
        self.assertEqual(verify_voice.said("एक लाख… एक साल!"), verify_voice.said("एक लाख, एक साल।"))

    def test_writing_prompts_list_the_forms_a_reel_may_name(self):
        text = build_prompts.render_writing(PILOT)
        for fid, form in dc.epfo_forms().items():
            self.assertIn("- Form {}: {}".format(fid, form["for"]), text)

    def test_retiming_keeps_image_approvals(self):
        shot = dc.load_json(PILOT / "episode.json")["shots"][0]
        before = dc.shot_spec_hash(shot, "keyframe")
        moved = dict(shot, start=shot["start"] + 1, end=shot["end"] + 1, sfx="changed")
        self.assertEqual(before, dc.shot_spec_hash(moved, "keyframe"))
        self.assertNotEqual(before, dc.shot_spec_hash(dict(shot, card_text=["changed"]), "keyframe"))


class TestNotARepeat(unittest.TestCase):
    """A new reel never repeats an earlier one, and a live reel is never posted twice (tools/topics.py, E11)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ep1 = self.tmp / PILOT.name
        shutil.copytree(PILOT, self.ep1, ignore=shutil.ignore_patterns("final", "build", "test", "lines", "checks", "posted.json"))
        self._done = topics.DONE_FILE
        topics.DONE_FILE = self.tmp / "topics-done.json"   # no old reels unless a test adds some

    def tearDown(self):
        topics.DONE_FILE = self._done
        shutil.rmtree(self.tmp, ignore_errors=True)

    def new(self, folder="ep02-uan-activate", title="UAN activate kaise karein?", **brief):
        """A new episode as Muse uploads it in N1: title, topic and repeat_check."""
        f = self.tmp / folder
        f.mkdir()
        ep = dc.load_json(ROOT / "templates" / "episode.template.json")
        num, _, slug = folder.partition("-")
        ep.update({"id": num, "slug": slug, "title": title, "created": "2026-11-12"})
        ep["brief"]["topic"] = title
        ep["brief"]["repeat_check"] = {"closest": "ep01", "different_because":
                                       "ep01 is about claims that come back rejected; this one is about activating a UAN first."}
        ep["brief"].update(brief)
        dc.save_json(f / "episode.json", ep)
        new_episode.prepare(f)
        return f

    def copy_of_ep01(self, folder="ep02-claim-wapas"):
        """ep01 again under a new number, with another amount: the repeat the checks must stop."""
        f = self.tmp / folder
        shutil.copytree(self.ep1, f, ignore=shutil.ignore_patterns("status.json"))
        ep = json.loads((f / "episode.json").read_text(encoding="utf-8").replace("₹2,00,000", "₹4,00,000"))
        ep.update({"id": "ep02", "slug": folder.split("-", 1)[1]})
        ep["brief"]["repeat_check"] = {"closest": "ep01", "different_because": "A bigger PF balance, so the viewer sees what is at stake."}
        dc.save_json(f / "episode.json", ep)
        new_episode.prepare(f)
        return f

    def checks(self, f, level="fail"):
        r, _, _ = validate.validate_episode(f, dc.brand())
        return {i["id"] for i in r.of(level) if i["id"].startswith("E11")}, r

    def test_a_new_topic_passes_at_its_first_upload(self):
        ids, r = self.checks(self.new())
        self.assertEqual(r.of("fail"), [])          # nothing else is asked of N1 yet either

    def test_the_same_topic_in_other_words_fails(self):
        ids, _ = self.checks(self.new(title="EPF claim rejected: kaise theek karein?"))
        self.assertIn("E11.1", ids)

    def test_a_close_topic_is_a_note_and_repeat_check_must_name_it(self):
        f = self.new(title="Claim reject hone ke baad kya karein?", repeat_check={"closest": "old-07", "different_because": "x"})
        ids, _ = self.checks(f)
        self.assertIn("E11.6", ids)
        self.assertIn("E11.1", self.checks(f, "warn")[0])
        ep = dc.load_json(f / "episode.json")
        ep["brief"]["repeat_check"] = {"closest": "ep01-claim-reject", "different_because":
                                       "ep01 explains why a claim is rejected; this one is only about what to do the day after."}
        dc.save_json(f / "episode.json", ep)
        self.assertEqual(self.checks(f)[0], set())

    def test_repeat_check_is_needed_once_a_reel_exists(self):
        ids, _ = self.checks(self.new(repeat_check={"closest": "", "different_because": ""}))
        self.assertIn("E11.6", ids)
        self.assertEqual(self.checks(self.ep1)[0], set())   # the first reel has nothing to repeat

    def test_a_copied_reel_fails_on_topic_hook_script_and_photos(self):
        f = self.copy_of_ep01()
        ids, _ = self.checks(f)
        self.assertTrue({"E11.1", "E11.2", "E11.3", "E11.4"} <= ids, ids)
        rep, text = check_episode.check(f, use_voice=False, use_ocr=False)
        self.assertEqual(rep.result(), "FIX")
        topic = next(x for x in rep.fix if x["where"] == "E11.1")
        self.assertIn("approve.py repeat-ok", topic["how"])
        self.assertIn("ep01-claim-reject", topic["how"])
        self.assertIn("Not a repeat", text)

    @unittest.skipIf(build_reel is None, "needs Pillow")
    def test_a_photo_saved_again_under_a_new_name_is_caught(self):
        from PIL import Image, ImageDraw
        photos = self.ep1 / "media" / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGB", (800, 600), (235, 235, 235))       # a stand-in for ep01's photo: shapes with clear edges
        d = ImageDraw.Draw(im)
        d.ellipse([90, 110, 390, 410], fill=(30, 30, 30))
        d.rectangle([470, 170, 730, 520], fill=(120, 120, 120))
        im.save(photos / "worker_phone.webp")
        f = self.new()
        (f / "media" / "photos").mkdir(parents=True, exist_ok=True)
        with Image.open(photos / "worker_phone.webp") as im:
            im.convert("RGB").resize((im.width // 2, im.height // 2)).save(f / "media" / "photos" / "owner.jpg", quality=70)
        ids, r = self.checks(f)
        self.assertIn("E11.4", ids)
        self.assertTrue(any("looks the same as" in i["msg"] for i in r.of("fail")))

    def test_one_number_per_episode_and_the_folder_matches(self):
        self.new()
        f = self.new(folder="ep02-pension-kab", title="Pension ka paisa kab milta hai?")
        ids, r = self.checks(f)
        self.assertIn("E11.5", ids)
        g = self.new(folder="ep03-nominee-add", title="Nominee kaise jodein?")
        ep = dc.load_json(g / "episode.json")
        ep["slug"] = "nominee-change"
        dc.save_json(g / "episode.json", ep)
        self.assertIn("E11.5", self.checks(g)[0])

    def test_reels_posted_before_the_repo_count_too(self):
        dc.save_json(topics.DONE_FILE, {"topics": [{"topic": "UAN activate kaise karein?", "posted": "2026-06-01"}]})
        ids, r = self.checks(self.new(repeat_check={"closest": "old-01", "different_because": "It is the same topic, said again."}))
        self.assertIn("E11.1", ids)
        self.assertTrue(any("old-01" in i["msg"] for i in r.of("fail")))

    def test_a_reel_made_in_another_repo_counts_as_its_own_episode(self):
        dc.save_json(topics.DONE_FILE, {"topics": [{"topic": "UAN activate kaise karein?", "episode": "ep03-uan-elsewhere",
                                                    "hook": "UAN mila, par login nahi hota?"}]})
        early = self.new(folder="ep02-pension-kab", title="Pension ka paisa kab milta hai?")
        later = self.new(folder="ep04-uan-activate")
        self.assertNotIn("ep03-uan-elsewhere", [o["id"] for o in topics.earlier(early)])   # it came after ep02
        self.assertIn("ep03-uan-elsewhere", [o["id"] for o in topics.earlier(later)])
        self.assertEqual(topics.resolve("ep03", topics.earlier(later))["id"], "ep03-uan-elsewhere")
        ids, r = self.checks(later)
        self.assertIn("E11.1", ids)                                                      # the same topic, repeated
        self.assertIn("Next episode number: ep05", topics.register(self.tmp))
        self.assertIn("| ep03-uan-elsewhere (made in another repo) |", topics.register(self.tmp))

    def test_a_person_can_allow_a_repeat_and_the_ok_lapses_when_it_changes(self):
        f = self.copy_of_ep01()
        cmd = [sys.executable, str(ROOT / "tools" / "approve.py"), "repeat-ok", str(f), "ep01", "topic", "--note", "Part 2 on purpose"]
        muse = subprocess.run(cmd + ["--by", "Muse"], capture_output=True, text=True)
        self.assertIn("NOT RECORDED", muse.stdout)
        subprocess.run(cmd + ["--by", PERSON], capture_output=True, text=True)
        ids, r = self.checks(f)
        self.assertNotIn("E11.1", ids)
        self.assertTrue(any(i["id"] == "E11.1" and PERSON in i["msg"] for i in r.of("info")))
        ep = dc.load_json(f / "episode.json")
        ep["brief"]["topic"] += " Sach mein?"
        dc.save_json(f / "episode.json", ep)
        self.assertIn("E11.1", self.checks(f)[0])

    def test_a_posted_reel_says_posted_and_is_never_posted_twice(self):
        live = {"url": "https://www.instagram.com/reel/DCx1abcDEF/", "posted_on": "2026-11-14", "post_it_from": "Asha"}
        dc.save_json(self.ep1 / "posted.json", live)
        rep, text = check_episode.check(self.ep1, use_voice=False, use_ocr=False)
        self.assertEqual(rep.result(), "POSTED")
        self.assertIn("Never post it again", text)
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "topics.py"), "--is-posted", str(self.ep1)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        f = self.new()
        self.assertNotEqual(subprocess.run([sys.executable, str(ROOT / "tools" / "topics.py"), "--is-posted", str(f)],
                                           capture_output=True).returncode, 0)
        dc.save_json(f / "posted.json", live)                          # the same link in a second episode
        self.assertIn("E11.7", self.checks(f)[0])
        dc.save_json(self.ep1 / "posted.json", {"url": "my reel", "posted_on": "14 Nov"})
        self.assertIn("E11.7", self.checks(self.ep1)[0])
        rep, _ = check_episode.check(self.ep1, use_voice=False, use_ocr=False)
        self.assertEqual(rep.result(), "POSTED")                       # still live, so still never posted again
        self.assertEqual(rep.fix, [])

    def test_the_register_lists_every_reel_and_the_next_number(self):
        self.new()
        text = topics.register(self.tmp)
        self.assertIn("Next episode number: ep03", text)
        self.assertIn("| ep01-claim-reject | PF claim reject kyun hota hai, aur kaise theek karein?", text)
        self.assertIn("## ep02-uan-activate", text)
        self.assertEqual(topics.check_text("EPF claim rejected: kaise theek karein?", self.tmp)[0], "REPEAT")
        self.assertEqual(topics.check_text("Pension ka paisa kab milta hai?", self.tmp)[0], "NEW")

    @unittest.skipIf(build_reel is None, "needs Pillow and numpy")
    def test_an_upload_that_changes_nothing_in_the_reel_does_not_rebuild_it(self):
        ep = self.tmp / "built"
        shutil.copytree(PILOT, ep, ignore=shutil.ignore_patterns("test", "checks"))
        video = ep / "media" / "final" / (PILOT.name + ".mp4")
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"a reel built earlier")           # what's in it doesn't matter: only whether its inputs changed
        (ep / "build").mkdir(exist_ok=True)
        dc.save_json(ep / "build" / "timeline.json", {"inputs": dc.reel_inputs_hash(ep), "length": 90, "shots": []})
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "build_reel.py"), str(ep), "--if-changed",
                              "--out", str(video)], capture_output=True, text=True, timeout=60)
        self.assertIn("nothing to build", out.stdout)
        before = dc.reel_inputs_hash(ep)
        (ep / "posted.json").write_text("{}")
        self.assertEqual(before, dc.reel_inputs_hash(ep))               # posting isn't a reason to rebuild
        e = dc.load_json(ep / "episode.json")
        e["title"] += "!"
        dc.save_json(ep / "episode.json", e)
        self.assertNotEqual(before, dc.reel_inputs_hash(ep))


def fake_portal_screenshot(path):
    """A made-up member portal page (no real account): a menu with the claim item and a button."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(ROOT / "brand" / "fonts" / "IBMPlexMono-Medium.ttf"), 34)
    im = Image.new("RGB", (1080, 1300), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1080, 90], fill=(46, 104, 178))
    d.text((40, 22), "Online Services", font=font, fill="white")
    for i, t in enumerate(["Claim (Form-31, 19, 10C & 10D)", "Track Claim Status", "Transfer Request"]):
        d.rectangle([40, 140 + i * 120, 1040, 230 + i * 120], outline=(200, 205, 215), width=2, fill=(246, 248, 252))
        d.text((70, 165 + i * 120), t, font=font, fill=(20, 30, 50))
    d.rectangle([300, 600, 780, 690], fill=(200, 60, 40))           # a block of one colour, to find again
    im.save(path)


@unittest.skipUnless(build_reel, "Pillow and numpy are needed for the reel builder")
class TestScreens(unittest.TestCase):
    """Member portal screenshots: shown as they are, with rings on what to tap, and checked with OCR."""

    def episode_with_screen(self, tmp, make_file=True):
        ep = Path(tmp) / PILOT.name
        shutil.copytree(PILOT, ep, ignore=shutil.ignore_patterns("final", "build", "test"))
        shot = ep / "media" / "screens" / "menu.png"
        shot.parent.mkdir(parents=True)
        if make_file:
            fake_portal_screenshot(shot)
        reel = json.loads((ep / "reel.json").read_text(encoding="utf-8"))
        reel["screens"] = {"menu": {"id": "SC1", "file": str(shot), "shows": "the Online Services menu, open",
                                    "must_show": ["Online Services", "Claim (Form-31, 19, 10C & 10D)"]}}
        reel["shots"]["S07"] = [{"type": "screen", "src": "menu", "tab": "MEMBER PORTAL", "y": 420, "at": 0.1,
                                 "marks": [{"box": [0.05, 0.12, 0.62, 0.17], "text": "Claim (Form-31, 19, 10C & 10D)",
                                            "on": "login"}]}]
        (ep / "reel.json").write_text(json.dumps(reel, ensure_ascii=False), encoding="utf-8")
        e = json.loads((ep / "episode.json").read_text(encoding="utf-8"))
        next(sh for sh in e["shots"] if sh["id"] == "S07")["card_text"] = ["MEMBER PORTAL"]
        (ep / "episode.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
        return ep

    def test_a_screenshot_is_shown_as_it_is_and_its_ring_lands_on_its_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.episode_with_screen(tmp)
            reel = build_reel.Reel(ep)
            self.assertEqual([p for p in reel.check_texts() if "placeholder" not in p], [])
            i = [s["id"] for s in reel.E.shots].index("S07")
            screen = reel.elements[i][0]
            self.assertEqual(screen.texts(), ["MEMBER PORTAL"])          # the screenshot's own words aren't card text
            self.assertGreater(screen.marks()[0]["at"], 0.5)              # the ring waits for "login"
            before, after = screen.art(screen.marks()[0]["at"] - 0.05), screen.art(10)
            self.assertNotEqual(before.tobytes(), after.tobytes())
            shot = reel.E.shots[i]
            self.assertGreaterEqual(shot["end"] - shot["start"], build_reel.Screen.HOLD - 0.01)   # time to find the button
            x0, y0, x1, y1 = screen.frame_box()
            self.assertTrue(0 <= x0 < x1 <= 1080 and 400 <= y0 < y1 <= 1240)
            frame = reel.render(reel.E.shots[i]["end"] - 0.05, header=False, caption=False, stills=True)
            # the red block in the screenshot keeps its colour: no halftone, no grey
            _, _, sx, sy, sw, sh = screen.layout()
            cx, cy = screen.centre()
            aw, ah = screen.size0()
            px = frame.getpixel((round(cx - aw / 2 + sx + 0.5 * sw), round(cy - ah / 2 + sy + 645 / 1300 * sh)))
            self.assertLess(max(abs(a - b) for a, b in zip(px[:3], (200, 60, 40))), 12)

    def test_a_missing_screenshot_shows_a_placeholder_and_waits_for_a_person(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.episode_with_screen(tmp, make_file=False)
            problems = build_reel.Reel(ep).check_texts()
            self.assertTrue(any(p.startswith("screen SC1 ") and "placeholder" in p for p in problems))
            rep = check_episode.Report()
            check_episode.reel_file(ep, rep)
            self.assertTrue(any(t.startswith("screenshot SC1") and "a person takes it" in t for t in rep.todo))
            self.assertFalse(rep.fix)

    def test_the_prompts_list_each_screenshot_and_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.episode_with_screen(tmp)
            text = build_prompts.render(ep)
            self.assertIn("## 1 · Screenshots (a person takes these)", text)
            self.assertIn("### SC1 · the Online Services menu, open (used in S07)", text)
            self.assertIn("It must show: `Online Services` · `Claim (Form-31, 19, 10C & 10D)`", text)
            self.assertIn("cover every personal detail with a solid box", text)

    def test_a_screenshot_label_is_read_letter_by_letter(self):
        shows = verify_media._shows
        # what OCR read on ep03's menu: no spaces after the commas, and CLAIM as CLAM
        self.assertTrue(shows("Claim (Form-31, 19, 10C & 10D)", [{"text": "CLAM(FORM-31,19,10C&10D)"}]))
        self.assertTrue(shows("Get Aadhaar OTP", [{"text": "Get"}, {"text": "Aadhaar OTP"}]))     # split in two
        self.assertFalse(shows("Proceed for Online Claim", [{"text": "Track Claim Status"}]))      # another button
        self.assertFalse(shows("Claim (Form-31, 19, 10C & 10D)", [{"text": "Claim (Form-13)"}]))   # another form

    def test_ocr_leaves_out_the_words_on_a_screenshot(self):
        lines = [{"text": "Claim (Form-31, 19, 10C & 10D)", "cx": 0.5, "cy": 0.3},
                 {"text": "MEMBER PORTAL", "cx": 0.1, "cy": 0.02},
                 {"text": "no box", "cx": None, "cy": None}]
        # the crop starts at y 336 and is 931 tall: line 1 is at (540, 615), inside the screenshot
        kept = verify_media.outside_screens(lines, [[100, 450, 980, 1200]], 336, 931, 1080)
        self.assertEqual([l["text"] for l in kept], ["MEMBER PORTAL", "no box"])

    @unittest.skipUnless(verify_media.ocr_engine()[0] is not None, "no OCR engine installed")
    def test_screenshots_show_their_words_and_the_report_gives_the_crop_and_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.episode_with_screen(tmp)
            path = ep / "reel.json"

            def check(change=None):
                reel = json.loads(path.read_text(encoding="utf-8"))
                if change:
                    change(reel)
                    path.write_text(json.dumps(reel, ensure_ascii=False), encoding="utf-8")
                return verify_media.check_screens(ep).text()

            def numbers(pattern, text):
                m = re.search(pattern + r'\[([\d., ]+)\]', text)
                self.assertIsNotNone(m, text)
                return [float(v) for v in m.group(1).split(",")]

            # a tall phone screenshot without a crop: the report gives the band round its words
            text = check()
            crop = numbers(r'SC1 · no crop, .*"crop": ', text)
            self.assertTrue(crop[0] == 0 and crop[2] == 1 and crop[1] <= 0.02 and 0.25 <= crop[3] <= 0.75, crop)
            # with the crop, the ring's box is in shares of the crop: the report gives it
            text = check(lambda r: r["screens"]["menu"].update(crop=crop))
            box = numbers(r'isn\'t on `Claim \(Form-31, 19, 10C & 10D\)`: put it at "box": ', text)
            text = check(lambda r: r["shots"]["S07"][0]["marks"][0].update(box=box))
            self.assertNotIn("FAIL", text)
            self.assertIn("S07 · the mark on SC1 sits on `Claim (Form-31, 19, 10C & 10D)`", text)
            # a word the page doesn't show goes to a person; a ring off its word goes to Muse
            check(lambda r: (r["screens"]["menu"]["must_show"].append("Proceed for Online Claim"),
                             r["shots"]["S07"][0]["marks"][0].update(box=[0.05, 0.80, 0.62, 0.90])))
            rep = check_episode.Report()
            check_episode.screenshots(ep, rep, use_ocr=True)
            self.assertTrue(any(p["where"] == "SC1" and "Proceed for Online Claim" in p["what"] for p in rep.person))
            self.assertTrue(any(f["where"] == "S07" and "put it at" in f["what"] for f in rep.fix))


class TestLogo(unittest.TestCase):
    def test_the_logo_files_are_outlines_with_pngs_beside_them(self):
        self.assertTrue((ROOT / dc.brand()["logo_file"]).exists())
        svgs = sorted((ROOT / "brand" / "assets" / "logo").glob("*.svg"))
        self.assertGreaterEqual(len(svgs), 5)
        for f in svgs:
            svg = f.read_text(encoding="utf-8")
            self.assertNotIn("<text", svg, f.name)            # letters are outlines: the same in any app
            self.assertIn("viewBox=", svg, f.name)
            self.assertTrue(f.with_suffix(".png").exists(), f.name)

    def test_the_logo_svgs_are_what_make_logo_draws(self):
        try:
            import make_logo
        except ImportError:
            self.skipTest("fontTools is needed to draw the logo")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(make_logo, "OUT", Path(tmp)), \
                mock.patch("builtins.print"):
            make_logo.main()
            made = sorted(Path(tmp).glob("*.svg"))
            self.assertEqual([f.name for f in made], [f.name for f in sorted((ROOT / "brand" / "assets" / "logo").glob("*.svg"))])
            for f in made:
                self.assertEqual(f.read_text(encoding="utf-8"),
                                 (ROOT / "brand" / "assets" / "logo" / f.name).read_text(encoding="utf-8"), f.name)


@unittest.skipUnless(verify_media.ocr_engine()[0] is not None, "no OCR engine installed")
class TestOcrOnStyleFrames(unittest.TestCase):
    """Uses the committed reference frames: the right shot passes, the wrong shot fails."""

    def test_right_frame_passes_and_wrong_frame_fails(self):
        frame = ROOT / "brand" / "assets" / "style-frames" / "s04-card.png"
        self.assertFalse(verify_media.check_keyframe(PILOT, "S04", frame).failed)
        self.assertTrue(verify_media.check_keyframe(PILOT, "S08", frame).failed)


if __name__ == "__main__":
    unittest.main()


FOCUS_SAMPLE = ROOT / "styles" / "focus" / "ep00-focus-sample"


class TestFocusTheme(unittest.TestCase):
    """The Focus theme (styles/focus/STYLE.md): an EPFO task shown on drawn screens."""

    def copy_sample(self, tmp):
        ep_dir = Path(tmp) / FOCUS_SAMPLE.name
        shutil.copytree(FOCUS_SAMPLE, ep_dir, ignore=shutil.ignore_patterns("final", "build", "lines"))
        return ep_dir

    def fresh_sources(self, reel, day="2026-11-10"):
        for spec in reel["screens"].values():
            for src in spec["sources"]:
                src["seen"] = day
            spec["sources"][0]["updated"] = day

    def focus_fails(self, ep_dir):
        """{check id: all its messages} for the Focus checks (E4.20 to E4.28) that fail."""
        r, _, _ = validate.validate_episode(ep_dir, dc.brand())
        out = {}
        for i in r.of("fail"):
            if i["id"].startswith("E4.2"):
                out[i["id"]] = (out.get(i["id"], "") + " | " + i["msg"]).strip(" |")
        return out

    def test_the_theme_settings_replace_the_story_shape(self):
        b = dc.for_style(dc.brand(), {"style": "focus"})
        self.assertEqual(b["chapters"], ["hook", "signoff"])
        self.assertTrue(b["free_shape"])
        self.assertEqual(b["rules"]["duration_seconds"], [40, 120])
        self.assertEqual(b["rules"]["tail_seconds"], dc.brand()["rules"]["tail_seconds"])   # the rest stays
        self.assertEqual(dc.for_style(dc.brand(), {})["chapters"], dc.brand()["chapters"])   # Kahani, as it was

    @unittest.skipIf(build_reel is None, "needs Pillow and numpy")
    def test_the_sample_is_built_as_a_focus_reel_in_the_brand(self):
        reel = build_reel.make_reel(FOCUS_SAMPLE, use_voice=False)
        self.assertEqual(type(reel).__name__, "FocusReel")
        self.assertEqual([p for p in reel.check_texts() if "placeholder" not in p], [])
        self.assertEqual(build_reel.logo_text(), "PF GURU JI")
        frame = reel.render(1.0)
        self.assertEqual(frame.size, (1080, 1920))
        self.assertIn("Mark Exit", reel.screen_words(6))                     # S07's drawn menu, not a card
        story = build_reel.make_reel(PILOT, use_voice=False)                  # a story reel stays a story reel
        self.assertIsInstance(story, build_reel.Reel)

    def test_a_screen_needs_fresh_official_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir = self.copy_sample(tmp)
            reel = dc.load_json(ep_dir / "reel.json")
            self.assertIn("E4.23", self.focus_fails(ep_dir))                  # the sample's sources aren't read yet
            self.fresh_sources(reel)
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                self.assertEqual(self.focus_fails(ep_dir), {})
            reel["screens"]["exit"]["sources"] = reel["screens"]["exit"]["sources"][1:]   # one source, not official
            reel["screens"]["exit"]["sources"][0]["kind"] = "video"
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                self.assertIn("two sources at least", self.focus_fails(ep_dir).get("E4.23", ""))

    def test_a_drawn_screen_shows_nobodys_details(self):
        spec = {"parts": [{"kind": "title", "text": "Welcome", "sub": "UAN 1012 3456 7890"},
                          {"kind": "row", "text": "Mobile", "value": "9876543210"},
                          {"kind": "row", "text": "PAN", "value": "ABCDE1234F"},
                          {"kind": "row", "text": "Masked", "value": "XXXX XXXX 1234"},
                          {"kind": "row", "text": "Joined", "value": "01/04/2023"}]}
        self.assertEqual(validate.personal_numbers(spec), ["UAN 1012 3456 7890", "9876543210", "ABCDE1234F"])
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir = self.copy_sample(tmp)
            reel = dc.load_json(ep_dir / "reel.json")
            self.fresh_sources(reel)
            reel["screens"]["home"]["parts"][1]["sub"] = "UAN 1012 3456 7890"
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                self.assertIn("E4.28", self.focus_fails(ep_dir))

    def test_the_walk_takes_the_viewer_to_every_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir = self.copy_sample(tmp)
            reel = dc.load_json(ep_dir / "reel.json")
            self.fresh_sources(reel)
            reel["shots"]["S07"][0]["do"] = [{"look": "markexit", "on": "Mark"}]    # Mark Exit, but no page opens
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                fails = self.focus_fails(ep_dir)
            self.assertIn("E4.27", fails)
            self.assertIn("nothing on screen took them there", fails["E4.27"])

    def test_a_focus_reel_uses_only_its_own_cards_and_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir = self.copy_sample(tmp)
            reel = dc.load_json(ep_dir / "reel.json")
            self.fresh_sources(reel)
            reel["shots"]["S02"] = [{"type": "stamp", "text": "GALTI"}]          # a story card in a Focus reel
            reel["shots"]["S08"][0]["do"][0]["on"] = "Dropdown"                  # a word the line doesn't say
            reel["shots"]["S09"][0]["do"][0]["write"] = "dateofexit"            # a part the screen doesn't have
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                msgs = self.focus_fails(ep_dir).get("E4.24", "")
            self.assertIn("isn't a card of the Focus style", msgs)
            self.assertIn("\"Dropdown\" isn't a word of its line", msgs)
            self.assertIn("\"dateofexit\" isn't a part of screen \"exit\"", msgs)

    def test_the_hook_opens_on_its_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep_dir = self.copy_sample(tmp)
            reel = dc.load_json(ep_dir / "reel.json")
            self.fresh_sources(reel)
            reel["shots"]["S01"] = [el for el in reel["shots"]["S01"] if el["type"] != "headline"]
            dc.save_json(ep_dir / "reel.json", reel)
            with mock.patch.object(dc, "today", return_value="2026-11-19"):
                self.assertIn("E4.20", self.focus_fails(ep_dir))

    def test_a_focus_episode_gets_the_focus_prompts_and_no_screenshot_list(self):
        writing = build_prompts.render_writing(FOCUS_SAMPLE)
        self.assertIn("Theme: Focus", writing)
        self.assertIn("THE STEPS COME FROM THE NEWEST PAGES", writing)
        self.assertNotIn("{{", writing)
        prompts = build_prompts.render(FOCUS_SAMPLE)
        self.assertIn("## 1 · Screens", prompts)
        self.assertNotIn("Screenshots", prompts.split("## 2 · Voice")[0])
        self.assertIsNone(verify_media.check_screens(FOCUS_SAMPLE))           # drawn screens: nothing to read back
