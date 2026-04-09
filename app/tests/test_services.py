import os
import json
import sqlite3
import sys
import tempfile
import time
import unittest
import importlib.util
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from app.cli.ingest_prompter import AutoYesIngestPrompter, NonInteractiveIngestPrompter
from app.config import get_request_max_output_tokens
from app.core.epub_processor import chunk_markdown_by_chapters
from app.core.manifest import Manifest
from app.core import monitor as monitor_module
from app.services import (
    book_management_service,
    evaluation_service,
    ingest_service,
    maintenance_service,
    publish_service,
    query_service,
)
from app.services.ingest_reporting import print_cost_estimate
from app.services.ingest_interaction import IngestPrompter, LowMatchAction, LowMatchDecision
from app.services.step_result import StepResult


workflow_spec = importlib.util.spec_from_file_location(
    "scripts_workflow",
    Path(project_root) / "scripts" / "workflow.py",
)
workflow = importlib.util.module_from_spec(workflow_spec)
assert workflow_spec.loader is not None
workflow_spec.loader.exec_module(workflow)


class FakePrompter(IngestPrompter):
    def __init__(
        self,
        low_match_action=LowMatchDecision(LowMatchAction.ABORT),
        toc_continue=True,
        chunking=True,
    ):
        self.low_match_action = low_match_action
        self.toc_continue = toc_continue
        self.chunking = chunking
        self.low_match_reviews = []
        self.toc_continue_reviews = []
        self.chunking_reviews = []

    def choose_low_match_action(self, review):
        self.low_match_reviews.append(review)
        return self.low_match_action

    def confirm_toc_continue(self, review, passed: bool) -> bool:
        self.toc_continue_reviews.append((review, passed))
        return self.toc_continue

    def confirm_chunking_without_toc(self, review) -> bool:
        self.chunking_reviews.append(review)
        return self.chunking


class PublishServiceTests(unittest.TestCase):
    def test_publish_continues_after_non_fatal_failure(self):
        calls = []

        def mark(name, result=True):
            def _fn(*args, **kwargs):
                calls.append(name)
                return result

            return _fn

        with (
            mock.patch.object(
                publish_service, "sync_glyphs", side_effect=mark("glyphs", StepResult.success())
            ),
            mock.patch.object(
                publish_service, "sync_notes", side_effect=mark("notes", StepResult.success())
            ),
            mock.patch.object(
                publish_service,
                "compute_related",
                side_effect=mark("related", StepResult.failed("stale")),
            ),
            mock.patch.object(
                publish_service, "refresh_stats", side_effect=mark("stats", StepResult.success())
            ),
            mock.patch.object(
                publish_service,
                "report_vector_backlog",
                side_effect=mark("backlog", StepResult.success()),
            ),
            mock.patch.object(
                publish_service,
                "run_integrity_check",
                side_effect=mark("integrity", StepResult.success()),
            ),
            mock.patch.object(
                publish_service, "build_site", side_effect=mark("site", StepResult.success())
            ),
            mock.patch.object(
                publish_service,
                "build_search_index",
                side_effect=mark("search", StepResult.skipped("node missing")),
            ),
            mock.patch.object(
                publish_service,
                "sync_vectors_to_postgres",
                side_effect=mark("vectors", StepResult.success()),
            ),
        ):
            ok = publish_service.publish(
                publish_service.PublishOptions(
                    reconcile_mode="none", sync_vectors=True, run_integrity=True
                )
            )

        self.assertTrue(ok)
        self.assertEqual(
            calls,
            ["glyphs", "notes", "related", "stats", "backlog", "integrity", "site", "search", "vectors"],
        )

    def test_publish_stops_on_fatal_failure(self):
        calls = []

        def mark(name, result=True):
            def _fn(*args, **kwargs):
                calls.append(name)
                return result

            return _fn

        with (
            mock.patch.object(
                publish_service, "sync_glyphs", side_effect=mark("glyphs", StepResult.success())
            ),
            mock.patch.object(
                publish_service,
                "sync_notes",
                side_effect=mark("notes", StepResult.failed("boom")),
            ),
            mock.patch.object(
                publish_service, "compute_related", side_effect=mark("related", StepResult.success())
            ),
        ):
            ok = publish_service.publish(publish_service.PublishOptions())

        self.assertFalse(ok)
        self.assertEqual(calls, ["glyphs", "notes"])


class WorkflowScriptTests(unittest.TestCase):
    def test_ship_uses_unsigned_commit_when_requested(self):
        args = SimpleNamespace(
            reconcile="none",
            sync_vectors=False,
            skip_integrity=False,
            no_gpg_sign=True,
            allow_preview=False,
            deploy_production=False,
        )
        run_cmd_calls = []

        def fake_run_cmd(cmd):
            run_cmd_calls.append(cmd)
            return 0

        def fake_subprocess_run(cmd, cwd=None, capture_output=False, text=False):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 1)
            if cmd == ["git", "-c", "commit.gpgsign=false", "commit", "-m", "new books"]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            mock.patch.object(workflow, "get_current_branch_name", return_value="main"),
            mock.patch.object(workflow, "publish_command", return_value=0),
            mock.patch.object(workflow, "run_cmd", side_effect=fake_run_cmd),
            mock.patch.object(workflow.subprocess, "run", side_effect=fake_subprocess_run),
        ):
            rc = workflow.ship_command(args)

        self.assertEqual(rc, 0)
        self.assertEqual(
            run_cmd_calls,
            [
                ["git", "add", "notes/", "index/", "blog/content/", "blog/data/"],
                ["git", "push"],
            ],
        )

    def test_ship_prints_pinentry_guidance_on_gpg_failure(self):
        args = SimpleNamespace(
            reconcile="none",
            sync_vectors=False,
            skip_integrity=False,
            no_gpg_sign=False,
            allow_preview=False,
            deploy_production=False,
        )
        output = StringIO()
        error = StringIO()

        def fake_subprocess_run(cmd, cwd=None, capture_output=False, text=False):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 1)
            if cmd == ["git", "commit", "-m", "new books"]:
                return subprocess.CompletedProcess(
                    cmd,
                    128,
                    "",
                    "error: gpg failed to sign the data:\n"
                    "gpg: signing failed: No pinentry\n"
                    "fatal: failed to write commit object\n",
                )
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            mock.patch.object(workflow, "get_current_branch_name", return_value="main"),
            mock.patch.object(workflow, "publish_command", return_value=0),
            mock.patch.object(workflow, "run_cmd", return_value=0) as run_cmd,
            mock.patch.object(workflow.subprocess, "run", side_effect=fake_subprocess_run),
            redirect_stdout(output),
            redirect_stderr(error),
        ):
            rc = workflow.ship_command(args)

        self.assertEqual(rc, 128)
        run_cmd.assert_called_once_with(
            ["git", "add", "notes/", "index/", "blog/content/", "blog/data/"]
        )
        combined = output.getvalue() + error.getvalue()
        self.assertIn("Git commit signing failed because pinentry was unavailable.", combined)
        self.assertIn("python3 scripts/workflow.py ship --no-gpg-sign", combined)

    def test_ship_defaults_to_preview_push_from_non_production_branch(self):
        args = SimpleNamespace(
            reconcile="none",
            sync_vectors=False,
            skip_integrity=False,
            no_gpg_sign=False,
            allow_preview=False,
            deploy_production=False,
        )
        output = StringIO()
        error = StringIO()
        run_cmd_calls = []

        def fake_run_cmd(cmd):
            run_cmd_calls.append(cmd)
            return 0

        def fake_subprocess_run(cmd, cwd=None, capture_output=False, text=False):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 1)
            if cmd == ["git", "commit", "-m", "new books"]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            mock.patch.object(workflow, "get_current_branch_name", return_value="feature/books"),
            mock.patch.object(workflow, "publish_command", return_value=0),
            mock.patch.object(workflow, "run_cmd", side_effect=fake_run_cmd),
            mock.patch.object(workflow.subprocess, "run", side_effect=fake_subprocess_run),
            redirect_stdout(output),
            redirect_stderr(error),
        ):
            rc = workflow.ship_command(args)

        self.assertEqual(rc, 0)
        self.assertEqual(
            run_cmd_calls,
            [
                ["git", "add", "notes/", "index/", "blog/content/", "blog/data/"],
                ["git", "push"],
            ],
        )
        self.assertIn("preview deployment", error.getvalue())

    def test_ship_allows_preview_push_when_requested(self):
        args = SimpleNamespace(
            reconcile="none",
            sync_vectors=False,
            skip_integrity=False,
            no_gpg_sign=False,
            allow_preview=True,
            deploy_production=False,
        )
        run_cmd_calls = []

        def fake_run_cmd(cmd):
            run_cmd_calls.append(cmd)
            return 0

        def fake_subprocess_run(cmd, cwd=None, capture_output=False, text=False):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 1)
            if cmd == ["git", "commit", "-m", "new books"]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            mock.patch.object(workflow, "get_current_branch_name", return_value="feature/books"),
            mock.patch.object(workflow, "publish_command", return_value=0),
            mock.patch.object(workflow, "run_cmd", side_effect=fake_run_cmd),
            mock.patch.object(workflow.subprocess, "run", side_effect=fake_subprocess_run),
        ):
            rc = workflow.ship_command(args)

        self.assertEqual(rc, 0)
        self.assertEqual(
            run_cmd_calls,
            [
                ["git", "add", "notes/", "index/", "blog/content/", "blog/data/"],
                ["git", "push"],
            ],
        )

    def test_ship_deploys_production_from_preview_branch_when_requested(self):
        args = SimpleNamespace(
            reconcile="none",
            sync_vectors=False,
            skip_integrity=False,
            no_gpg_sign=False,
            allow_preview=False,
            deploy_production=True,
        )
        run_cmd_calls = []

        def fake_run_cmd(cmd):
            run_cmd_calls.append(cmd)
            return 0

        def fake_subprocess_run(cmd, cwd=None, capture_output=False, text=False):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(cmd, 1)
            if cmd == ["git", "commit", "-m", "new books"]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            mock.patch.object(workflow, "get_current_branch_name", return_value="feature/books"),
            mock.patch.object(workflow, "publish_command", return_value=0),
            mock.patch.object(workflow, "run_cmd", side_effect=fake_run_cmd),
            mock.patch.object(workflow.subprocess, "run", side_effect=fake_subprocess_run),
        ):
            rc = workflow.ship_command(args)

        self.assertEqual(rc, 0)
        self.assertEqual(
            run_cmd_calls,
            [
                ["git", "add", "notes/", "index/", "blog/content/", "blog/data/"],
                ["git", "push"],
                ["npx", "vercel", "deploy", "--prod", "--yes"],
            ],
        )


class MonitorTests(unittest.TestCase):
    def test_submit_job_preserves_result_order_under_concurrency(self):
        monitor = monitor_module.Monitor(client=None)
        requests = [
            {"request": {"max_tokens": 1, "model": "test-model"}, "file_metadata": {}}
            for _ in range(3)
        ]

        def fake_process(index, request, total):
            delays = {0: 0.03, 1: 0.0, 2: 0.01}
            time.sleep(delays[index])
            return {"index": index, "status": "SUCCESS", "response": f"chunk-{index}"}

        with (
            mock.patch.object(monitor, "_process_request", side_effect=fake_process),
            mock.patch.object(monitor, "_save_results_cache"),
            mock.patch.object(monitor_module, "INGEST_CONCURRENCY", 2),
        ):
            job = monitor.submit_job(requests)

        self.assertEqual([result["index"] for result in job.results], [0, 1, 2])
        self.assertEqual(job.state, "SUCCEEDED")

    def test_normalize_usage_keeps_cache_creation_tokens(self):
        usage = monitor_module.Monitor._normalize_usage(
            {
                "input_tokens": 1000,
                "output_tokens": 200,
                "cached_input_tokens": 300,
                "cache_creation_input_tokens": 400,
            }
        )

        self.assertEqual(usage["input_tokens"], 1000)
        self.assertEqual(usage["cached_input_tokens"], 300)
        self.assertEqual(usage["cache_creation_input_tokens"], 400)


class MaintenanceServiceTests(unittest.TestCase):
    def test_run_reconcile_builds_apply_all_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "scripts" / "reconcile_vectors.py"
            script_path.parent.mkdir(parents=True)
            script_path.write_text("#!/usr/bin/env python3\n")

            with (
                mock.patch.object(maintenance_service, "PROJECT_ROOT", root),
                mock.patch.object(
                    maintenance_service,
                    "_stream_command",
                    return_value=StepResult.success(),
                ) as stream,
            ):
                ok = maintenance_service.run_reconcile("full")

        self.assertTrue(ok.ok)
        stream.assert_called_once_with(
            [maintenance_service.PYTHON, str(script_path), "--apply-all"], cwd=root
        )

    def test_run_integrity_check_builds_allow_drift_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "scripts" / "check_integrity.py"
            script_path.parent.mkdir(parents=True)
            script_path.write_text("#!/usr/bin/env python3\n")

            with (
                mock.patch.object(maintenance_service, "PROJECT_ROOT", root),
                mock.patch.object(
                    maintenance_service,
                    "_stream_command",
                    return_value=StepResult.success(),
                ) as stream,
            ):
                ok = maintenance_service.run_integrity_check(allow_vector_drift=True)

        self.assertTrue(ok.ok)
        stream.assert_called_once_with(
            [maintenance_service.PYTHON, str(script_path), "--allow-vector-drift"], cwd=root
        )

    def test_sync_vectors_to_postgres_skips_without_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "scripts" / "migrate-vectors.py"
            script_path.parent.mkdir(parents=True)
            script_path.write_text("#!/usr/bin/env python3\n")

            with (
                mock.patch.object(maintenance_service, "PROJECT_ROOT", root),
                mock.patch.object(
                    maintenance_service,
                    "_stream_command",
                    return_value=StepResult.success(),
                ) as stream,
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                ok = maintenance_service.sync_vectors_to_postgres()

        self.assertTrue(ok.ok)
        self.assertTrue(ok.is_skipped)
        stream.assert_not_called()


class IngestServiceInteractionTests(unittest.TestCase):
    def test_check_chunking_warning_delegates_to_prompter(self):
        prompter = FakePrompter(chunking=True)
        uploaded_files = {"book.pdf": {"estimated_tokens": 250000}}

        ok = ingest_service.check_chunking_warning(
            uploaded_files, use_manual_toc=False, prompter=prompter
        )

        self.assertTrue(ok)
        self.assertEqual(len(prompter.chunking_reviews), 1)
        review = prompter.chunking_reviews[0]
        self.assertEqual(review.chunked_files, [("book.pdf", 250000)])
        self.assertFalse(review.has_toc)

    def test_check_chunking_warning_uses_model_specific_limit(self):
        prompter = FakePrompter(chunking=True)
        uploaded_files = {"book.pdf": {"estimated_tokens": 250000}}

        ok = ingest_service.check_chunking_warning(
            uploaded_files,
            use_manual_toc=False,
            prompter=prompter,
            model_id="claude-sonnet-4-6",
        )

        self.assertTrue(ok)
        self.assertEqual(prompter.chunking_reviews, [])

    def test_validate_toc_matches_uses_manual_toc_from_prompter(self):
        uploaded_files = {
            "book.epub": {"format": "markdown", "toc": ["Old Chapter"], "text": "body text"}
        }
        prompter = FakePrompter(
            low_match_action=LowMatchDecision(LowMatchAction.MANUAL_TOC),
            toc_continue=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            toc_path = Path(temp_dir) / "toc.txt"
            toc_path.write_text("Manual Chapter\n", encoding="utf-8")
            prompter.low_match_action = LowMatchDecision(
                LowMatchAction.MANUAL_TOC, str(toc_path)
            )

            with (
                mock.patch("app.core.epub_processor.parse_manual_toc", return_value=[("chapter", "Manual Chapter")]),
                mock.patch("app.core.epub_processor.get_flat_toc", return_value=["Manual Chapter"]),
                mock.patch(
                    "app.core.epub_processor.test_toc_matches",
                    side_effect=[
                        {"matched": [], "unmatched": ["Old Chapter"], "match_rate": 0.0},
                        {"matched": [("Manual Chapter", "ctx")], "unmatched": [], "match_rate": 1.0},
                    ],
                ),
            ):
                ok = ingest_service.validate_toc_matches(uploaded_files, prompter)

        self.assertTrue(ok)
        self.assertEqual(uploaded_files["book.epub"]["toc"], ["Manual Chapter"])
        self.assertEqual(uploaded_files["book.epub"]["toc_structured"], [("chapter", "Manual Chapter")])
        self.assertEqual(len(prompter.low_match_reviews), 1)
        self.assertEqual(prompter.toc_continue_reviews, [])

    def test_validate_toc_matches_prompts_when_match_rate_is_below_100_percent(self):
        uploaded_files = {
            "book.epub": {
                "format": "markdown",
                "toc": [f"Chapter {i}" for i in range(1, 11)],
                "text": "body text",
            }
        }
        prompter = FakePrompter(toc_continue=True)

        with mock.patch(
            "app.core.epub_processor.test_toc_matches",
            return_value={
                "matched": [(f"Chapter {i}", "ctx") for i in range(1, 10)],
                "unmatched": ["Chapter 10"],
                "match_rate": 0.9,
            },
        ):
            ok = ingest_service.validate_toc_matches(uploaded_files, prompter)

        self.assertTrue(ok)
        self.assertEqual(len(prompter.toc_continue_reviews), 1)
        _review, passed = prompter.toc_continue_reviews[0]
        self.assertTrue(passed)

    def test_auto_yes_prompter_accepts_reviews(self):
        review = ingest_service.TocValidationReview(
            filename="book.epub",
            toc_count=3,
            match_rate=0.2,
            matched_titles=[],
            unmatched_titles=["Chapter 1"],
        )
        chunk_review = ingest_service.ChunkingReview(
            chunked_files=[("book.pdf", 250000)],
            max_tokens=180000,
            has_toc=False,
        )
        prompter = AutoYesIngestPrompter()

        self.assertEqual(
            prompter.choose_low_match_action(review),
            LowMatchDecision(LowMatchAction.PROCEED),
        )
        self.assertTrue(prompter.confirm_toc_continue(review, passed=False))
        self.assertTrue(prompter.confirm_chunking_without_toc(chunk_review))

    def test_non_interactive_prompter_aborts_on_judgment_calls(self):
        review = ingest_service.TocValidationReview(
            filename="book.epub",
            toc_count=3,
            match_rate=0.2,
            matched_titles=[],
            unmatched_titles=["Chapter 1"],
        )
        chunk_review = ingest_service.ChunkingReview(
            chunked_files=[("book.pdf", 250000)],
            max_tokens=180000,
            has_toc=False,
        )
        prompter = NonInteractiveIngestPrompter()

        self.assertEqual(
            prompter.choose_low_match_action(review),
            LowMatchDecision(LowMatchAction.ABORT),
        )
        self.assertTrue(prompter.confirm_toc_continue(review, passed=True))
        self.assertFalse(prompter.confirm_chunking_without_toc(chunk_review))


class TocInjectionFallbackTests(unittest.TestCase):
    def test_chunking_can_map_generic_chapter_markers_to_manual_titles(self):
        markdown = (
            "Front matter\n\n"
            "Chapter One\n\n"
            "First body.\n\n"
            "Chapter Two\n\n"
            "Second body.\n\n"
            "Chapter Three\n\n"
            "Third body.\n"
        )
        toc = ["The Search Begins", "Prison and Escape", "The Human Machine"]

        chunks = chunk_markdown_by_chapters(markdown, max_tokens=10_000, toc=toc)

        combined = "\n\n".join(chunks)
        self.assertIn("## The Search Begins", combined)
        self.assertIn("## Prison and Escape", combined)
        self.assertIn("## The Human Machine", combined)

    def test_simple_token_chunking_rebalances_tiny_tail_chunk(self):
        paragraph = ("word " * 200).strip()
        tail_paragraph = ("word " * 120).strip()
        markdown = "\n\n".join(
            [paragraph, paragraph, paragraph, paragraph, tail_paragraph]
        )

        chunks = chunk_markdown_by_chapters(markdown, max_tokens=600)

        self.assertEqual(len(chunks), 2)


class ManifestTests(unittest.TestCase):
    def test_chunk_local_toc_guidance_omits_non_chunk_chapters(self):
        manifest = Manifest(client=None)
        chunk = "## Alpha\n\ntext\n\n## Beta\n\ntext"

        chunk_toc, chunk_toc_structured = manifest._extract_chunk_toc(
            chunk,
            toc=["Alpha", "Beta", "Gamma"],
            toc_structured=None,
        )
        guidance = manifest._build_chapter_guidance(
            toc=chunk_toc,
            toc_structured=chunk_toc_structured,
            location_label="chunk",
        )

        self.assertIn("Alpha", guidance)
        self.assertIn("Beta", guidance)
        self.assertNotIn("Gamma", guidance)

    def test_long_context_manifest_uses_cached_system_prompt(self):
        manifest = Manifest(client=None, model_id="claude-sonnet-4-6")

        request = manifest._build_text_request_payload("book body", "shared prompt")

        self.assertEqual(request["max_tokens"], get_request_max_output_tokens("claude-sonnet-4-6"))
        self.assertEqual(request["messages"][0]["content"], "book body")
        self.assertEqual(request["system"][0]["text"], "shared prompt")
        self.assertEqual(request["system"][0]["cache_control"], {"type": "ephemeral"})

    def test_dense_book_chunk_size_expands_for_long_context_models(self):
        manifest = Manifest(client=None, model_id="claude-sonnet-4-6")

        chunk_tokens = manifest._calculate_smart_chunk_size(485_041, 51)

        self.assertGreater(chunk_tokens, 60_000)
        self.assertLessEqual(chunk_tokens, 100_000)

    def test_should_create_chunk_plan_for_extra_long_book_with_toc(self):
        manifest = Manifest(client=None, model_id="claude-sonnet-4-6")

        should_plan = manifest.should_create_chunk_plan(
            {
                "format": "markdown",
                "estimated_tokens": 485_041,
                "toc": [f"Chapter {i}" for i in range(1, 52)],
            }
        )

        self.assertTrue(should_plan)

    def test_build_chunk_specs_from_plan_uses_start_anchors(self):
        manifest = Manifest(client=None, model_id="claude-sonnet-4-6")
        text = (
            "Alpha chapter opening paragraph with detail.\n\n"
            "Alpha continuation.\n\n"
            "Beta chapter opening paragraph with unique planned anchor text.\n\n"
            "Beta continuation.\n\n"
            "Gamma chapter opening paragraph with another unique planned anchor.\n\n"
            "Gamma continuation."
        )
        chunk_plan = {
            "chunks": [
                {"chunk_number": 1, "chapter_titles": ["Alpha"], "start_anchor": None},
                {
                    "chunk_number": 2,
                    "chapter_titles": ["Beta"],
                    "start_anchor": "Beta chapter opening paragraph with unique planned anchor text.",
                },
                {
                    "chunk_number": 3,
                    "chapter_titles": ["Gamma"],
                    "start_anchor": "Gamma chapter opening paragraph with another unique planned anchor.",
                },
            ]
        }

        specs = manifest._build_chunk_specs_from_plan(text, chunk_plan, max_chunk_tokens=10_000)

        self.assertEqual(len(specs), 3)
        self.assertIn("Alpha continuation", specs[0]["text"])
        self.assertTrue(specs[1]["text"].startswith("Beta chapter opening"))
        self.assertEqual(specs[2]["chapter_titles"], ["Gamma"])

    def test_parse_chunk_plan_response_rejects_toc_mismatch(self):
        manifest = Manifest(client=None, model_id="claude-sonnet-4-6")
        file_data = {"toc": ["Alpha", "Beta"]}

        parsed = manifest.parse_chunk_plan_response(
            '{"chunks":[{"chunk_number":1,"chapter_titles":["Alpha"],"start_anchor":null},{"chunk_number":2,"chapter_titles":["Gamma"],"start_anchor":"Gamma start"}]}',
            file_data,
        )

        self.assertIsNone(parsed)


class IngestReportingTests(unittest.TestCase):
    def test_print_cost_estimate_reports_cache_reads_and_writes(self):
        results = [
            {
                "model": "claude-sonnet-4-6",
                "usage": {
                    "input_tokens": 100_000,
                    "output_tokens": 10_000,
                    "cached_input_tokens": 20_000,
                    "cache_creation_input_tokens": 5_000,
                },
            }
        ]

        output = StringIO()
        with redirect_stdout(output):
            print_cost_estimate(results)

        rendered = output.getvalue()
        self.assertIn("input 125,000", rendered)
        self.assertIn("cache write: 5,000", rendered)
        self.assertIn("cache read: 20,000", rendered)


class IngestPlanningFlowTests(unittest.TestCase):
    def test_process_requests_skips_planning_in_retry_mode(self):
        manifest = mock.Mock()
        manifest.create_batch_job.return_value = []
        runtime = SimpleNamespace(manifest=manifest, monitor=mock.Mock())

        with mock.patch.object(ingest_service, "submit_requests", return_value=None):
            ingest_service._process_requests(runtime, uploaded_files={}, retry_mode=True)

        manifest.get_chunk_plan_requests.assert_not_called()


class QueryServiceTests(unittest.TestCase):
    def test_load_concept_registry_reads_from_repo_index_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index_dir = Path(temp_dir)
            (index_dir / "_concepts.json").write_text(
                '{"concepts":{"alpha":{"books":["book-a"]}}}', encoding="utf-8"
            )

            registry = query_service.load_concept_registry(index_dir=index_dir)

        self.assertIn("alpha", registry["concepts"])

    def test_get_book_concepts_reads_canonical_index_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index_dir = Path(temp_dir)
            (index_dir / "book-a.json").write_text(
                """
                {
                  "book": {"title": "Book A"},
                  "claims": [
                    {"concepts": ["alpha", "beta"]},
                    {"concepts": ["beta", "gamma"]}
                  ]
                }
                """.strip(),
                encoding="utf-8",
            )

            concepts = query_service.get_book_concepts(index_dir=index_dir)

        self.assertEqual(concepts["book-a"]["title"], "Book A")
        self.assertEqual(concepts["book-a"]["concepts"], {"alpha", "beta", "gamma"})

    def test_compare_books_uses_fuzzy_title_matching(self):
        fake_book_concepts = {
            "book-a": {"title": "Book A", "concepts": {"alpha", "beta"}},
            "book-b": {"title": "Book B", "concepts": {"beta", "gamma"}},
        }

        with mock.patch.object(
            query_service, "get_book_concepts", return_value=fake_book_concepts
        ):
            comparison, missing = query_service.compare_books("book a", "book-b")

        self.assertIsNone(missing)
        self.assertEqual(comparison.shared, ["beta"])
        self.assertEqual(comparison.only1, ["alpha"])
        self.assertEqual(comparison.only2, ["gamma"])


class BookManagementServiceTests(unittest.TestCase):
    def test_delete_book_dry_run_reports_existing_files_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_dir = Path(temp_dir) / "notes"
            index_dir = Path(temp_dir) / "index"
            notes_dir.mkdir()
            index_dir.mkdir()
            (notes_dir / "sample.md").write_text("# Sample\n", encoding="utf-8")
            (index_dir / "sample.json").write_text(
                '{"book":{"title":"Sample"}}', encoding="utf-8"
            )

            with (
                mock.patch.object(book_management_service, "NOTES_DIR", str(notes_dir)),
                mock.patch.object(book_management_service, "INDEX_DIR", str(index_dir)),
            ):
                result = book_management_service.delete_book("sample", dry_run=True)

        self.assertTrue(result.found)
        self.assertTrue(result.notes_exists)
        self.assertTrue(result.index_exists)
        self.assertEqual(result.book_title, "Sample")

    def test_rename_book_dry_run_detects_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_dir = Path(temp_dir) / "notes"
            index_dir = Path(temp_dir) / "index"
            notes_dir.mkdir()
            index_dir.mkdir()
            (notes_dir / "old.md").write_text("# Old\n", encoding="utf-8")
            (notes_dir / "new.md").write_text("# New\n", encoding="utf-8")

            with (
                mock.patch.object(book_management_service, "NOTES_DIR", str(notes_dir)),
                mock.patch.object(book_management_service, "INDEX_DIR", str(index_dir)),
            ):
                result = book_management_service.rename_book("old", "new", dry_run=True)

        self.assertTrue(result.source_found)
        self.assertTrue(result.destination_exists)

    def test_rename_book_allows_index_only_cleanup_when_note_already_matches_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_dir = Path(temp_dir) / "notes"
            index_dir = Path(temp_dir) / "index"
            notes_dir.mkdir()
            index_dir.mkdir()

            (notes_dir / "new.md").write_text("# New\n", encoding="utf-8")
            (index_dir / "old.json").write_text(
                json.dumps({"book": {"title": "old"}, "claims": []}),
                encoding="utf-8",
            )

            vectors_db = index_dir / "vectors.db"
            conn = sqlite3.connect(vectors_db)
            conn.execute("CREATE TABLE claims (book_name TEXT)")
            conn.execute("INSERT INTO claims (book_name) VALUES (?)", ("old",))
            conn.commit()
            conn.close()

            concepts_path = index_dir / "_concepts.json"
            concepts_path.write_text(
                json.dumps(
                    {
                        "concepts": {
                            "sample": {
                                "id": "sample",
                                "label": "Sample",
                                "book_claims": {"old": 2},
                                "books": ["old"],
                                "claim_count": 2,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(book_management_service, "NOTES_DIR", str(notes_dir)),
                mock.patch.object(book_management_service, "INDEX_DIR", str(index_dir)),
                mock.patch.object(book_management_service, "VECTORS_DB_PATH", str(vectors_db)),
                mock.patch.object(book_management_service, "CONCEPTS_PATH", str(concepts_path)),
            ):
                result = book_management_service.rename_book("old", "new", dry_run=False)

            self.assertTrue(result.source_found)
            self.assertFalse(result.destination_exists)
            self.assertEqual(result.updated_claims, 1)
            self.assertEqual(result.updated_concepts, 1)
            self.assertFalse((index_dir / "old.json").exists())
            self.assertTrue((index_dir / "new.json").exists())

            renamed_index = json.loads((index_dir / "new.json").read_text(encoding="utf-8"))
            self.assertEqual(renamed_index["book"]["title"], "new")

            conn = sqlite3.connect(vectors_db)
            old_count = conn.execute(
                "SELECT COUNT(*) FROM claims WHERE book_name = ?",
                ("old",),
            ).fetchone()[0]
            new_count = conn.execute(
                "SELECT COUNT(*) FROM claims WHERE book_name = ?",
                ("new",),
            ).fetchone()[0]
            conn.close()
            self.assertEqual(old_count, 0)
            self.assertEqual(new_count, 1)

            concepts = json.loads(concepts_path.read_text(encoding="utf-8"))
            sample = concepts["concepts"]["sample"]
            self.assertEqual(sample["book_claims"], {"new": 2})
            self.assertEqual(sample["books"], ["new"])


class EvaluationServiceTests(unittest.TestCase):
    def test_evaluate_notes_computes_quality_indicators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notes_dir = Path(temp_dir) / "notes"
            notes_dir.mkdir()
            note_path = notes_dir / "sample.md"
            note_path.write_text(
                "# Sample\n\n## Metadata\n- Thesis: X\n- Topics: Y\n- Categories: Z\n\n### Chapter 1\nSentence one.\nSentence two.\n",
                encoding="utf-8",
            )

            with mock.patch.object(evaluation_service, "NOTES_DIR", str(notes_dir)):
                evaluator = evaluation_service.BookEvaluator("sample")
                metrics = evaluator.evaluate_notes()

        self.assertEqual(metrics["headings"]["h3"], 1)
        self.assertTrue(metrics["quality_indicators"]["has_metadata_section"])
        self.assertEqual(metrics["quality_indicators"]["completeness_score"], 1.0)

    def test_calculate_overall_score_combines_available_sections(self):
        evaluator = evaluation_service.BookEvaluator("sample")
        result = evaluator.calculate_overall_score(
            {
                "notes": {"quality_indicators": {"completeness_score": 1.0}},
                "index": {"quality_score": 0.5},
                "embeddings": {"quality_score": 1.0},
            }
        )

        self.assertAlmostEqual(result["score"], (1.0 + 0.5 + 1.0) / 3)
        self.assertEqual(result["rating"], "Good ⭐⭐⭐⭐")


if __name__ == "__main__":
    unittest.main()
