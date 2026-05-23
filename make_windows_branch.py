#!/usr/bin/env python3
"""make_windows_branch.py ΓÇö Build or refresh a Windows-compatible mailman branch.

Takes a branch that was prepared for upstream (with colon-named template
files) and produces a Windows-compatible branch by renaming all
``src/mailman/templates/**/*:*.txt`` files to use ``_`` instead of ``:``.

Typical usage
-------------
Fresh build from upstream master::

    python make_windows_branch.py

Build from a specific PR branch::

    python make_windows_branch.py --source pr/safe-rename --output windows/safe-rename

Refresh the main windows branch after rebasing::

    python make_windows_branch.py --source rename --output windows

Upstream remote is added automatically on first run if not present.

Branch strategy
---------------
upstream/main  ΓöÇΓöÇ pr/safe-rename (PR branch, colon files)
                Γöé
                ΓööΓöÇ rename        (personal: just the : -> _ renames)
                        Γöé
                        ΓööΓöÇ windows/safe-rename  ΓåÉ what this script produces
                                 (pr branch + rename merged)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------


def _checkout_b(output, source):
    """``git checkout -b output source``, tolerating Windows colon-file errors.

    On Windows ``git checkout`` emits "unable to create file ΓÇª: Invalid
    argument" for every colon-named template file but still sets HEAD and
    populates the index correctly.  We run it with ``core.protectNTFS=false``
    so git's own path-validation layer doesn't abort first, then verify that
    we actually landed on the right branch.
    """
    if sys.platform == "win32":
        result = subprocess.run(
            ["git", "-c", "core.protectNTFS=false",
             "checkout", "-b", output, source],
            capture_output=True, text=True,
        )
        # Print stderr so the caller can see the colon-file warnings.
        if result.stderr:
            for line in result.stderr.splitlines():
                print(f"    git: {line}")
        actual = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
        ).strip()
        if actual != output:
            raise RuntimeError(
                f"checkout failed: expected branch '{output}', got '{actual}'"
            )
    else:
        subprocess.run(
            ["git", "checkout", "-b", output, source], check=True
        )


def extract_colon_files_from_index(repo_root):
    """Windows only: colon files weren't written by checkout; read them from
    the object store and write them with ``_`` names.

    Returns a list of ``(old_Path, new_Path)`` pairs (same format as
    ``rename_template_files``).  ``old_Path`` does *not* exist on disk ΓÇö
    it is only used by ``stage_renames`` as the index key to ``git rm``.
    """
    if sys.platform != "win32":
        return []

    ls = subprocess.check_output(["git", "ls-files"], text=True)
    renames = []
    for rel in ls.splitlines():
        if ":" not in Path(rel).name:
            continue
        new_rel = rel.replace(":", "_")
        new_abs = repo_root / new_rel
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        content = subprocess.run(
            ["git", "cat-file", "blob", f":{rel}"],
            capture_output=True, check=True,
        ).stdout
        new_abs.write_bytes(content)
        renames.append((repo_root / rel, new_abs))
        print(f"    extracted  {rel}")
        print(f"           ΓåÆ   {new_rel}")
    return renames

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPSTREAM_URL = "https://gitlab.com/mailman/mailman.git"
UPSTREAM_REMOTE = "upstream"
TEMPLATE_DIRS = [
    "src/mailman/templates",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(*args, capture=False, check=True, **kwargs):
    """Run a command, print it, and return the CompletedProcess."""
    flat = [str(a) for a in args]
    print("  $", " ".join(flat))
    result = subprocess.run(
        flat,
        capture_output=capture,
        text=True,
        check=check,
        **kwargs,
    )
    return result


def git(*args, capture=False, check=True):
    return run("git", *args, capture=capture, check=check)


def current_branch():
    return git("rev-parse", "--abbrev-ref", "HEAD", capture=True).stdout.strip()


def branch_exists(name):
    result = git("rev-parse", "--verify", name, capture=True, check=False)
    return result.returncode == 0


def remote_exists(name):
    result = git("remote", "get-url", name, capture=True, check=False)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def ensure_upstream_remote():
    """Add the upstream remote if it is not already present."""
    if not remote_exists(UPSTREAM_REMOTE):
        print(f"\n[+] Adding remote '{UPSTREAM_REMOTE}' ΓåÆ {UPSTREAM_URL}")
        git("remote", "add", UPSTREAM_REMOTE, UPSTREAM_URL)
    print(f"\n[+] Fetching {UPSTREAM_REMOTE} ΓÇª")
    git("fetch", UPSTREAM_REMOTE)


def rename_template_files(repo_root):
    """Rename : ΓåÆ _ in template filenames under TEMPLATE_DIRS.

    Returns the list of (old_path, new_path) pairs that were renamed.
    """
    renames = []
    for rel_dir in TEMPLATE_DIRS:
        base = Path(repo_root) / rel_dir
        if not base.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                if ":" in filename:
                    old = Path(dirpath) / filename
                    new = Path(dirpath) / filename.replace(":", "_")
                    old.rename(new)
                    renames.append((old, new))
                    print(f"    renamed  {old.relative_to(repo_root)}")
                    print(f"          ΓåÆ  {new.relative_to(repo_root)}")
    return renames


def stage_renames(repo_root, renames):
    """Stage the renamed files (git rm old, git add new)."""
    for old, new in renames:
        rel_old = str(old.relative_to(repo_root)).replace("\\", "/")
        rel_new = str(new.relative_to(repo_root)).replace("\\", "/")
        git("rm", "--cached", "-f", rel_old, check=False)
        git("add", rel_new)


def make_windows_branch(source, output, repo_root, message):
    """Create *output* from *source* with template renames applied.

    1. Create / reset *output* to *source*.
    2. Rename colon template filenames.
    3. Commit the renames.
    """
    saved = current_branch()

    print(f"\n[+] Creating branch '{output}' from '{source}' ΓÇª")
    if branch_exists(output):
        git("branch", "-D", output)
    _checkout_b(output, source)

    print(f"\n[+] Renaming template files ΓÇª")
    # On POSIX the colon files are on disk; on Windows they were never written
    # so we extract them from the object store instead.
    renames = rename_template_files(repo_root)
    renames += extract_colon_files_from_index(repo_root)
    if renames:
        stage_renames(repo_root, renames)
        git("commit", "-m", message)
        print(f"    {len(renames)} file(s) renamed and committed.")
    else:
        print("    Nothing to rename ΓÇö files already use '_' separators.")

    return saved


def merge_rename_branch(rename_branch, output):
    """Merge *rename_branch* into the current HEAD (which is *output*)."""
    if not branch_exists(rename_branch):
        print(f"\n[!] Branch '{rename_branch}' not found ΓÇö skipping merge.")
        return
    print(f"\n[+] Merging '{rename_branch}' into '{output}' ΓÇª")
    git("merge", "--no-ff", rename_branch,
        "-m", f"Merge {rename_branch} into {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--source",
        default=f"{UPSTREAM_REMOTE}/main",
        help=(
            "Branch or ref to base the output on.  "
            f"Default: {UPSTREAM_REMOTE}/main"
        ),
    )
    p.add_argument(
        "--output",
        default="windows",
        help="Name of the Windows branch to create/replace.  Default: windows",
    )
    p.add_argument(
        "--rename-branch",
        default="rename",
        help=(
            "Branch that holds the Windows-port changes (lazr shim, "
            "safe_rename, skipWindows, etc.).  Merged into --output after "
            "the template renames.  Default: rename"
        ),
    )
    p.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetching the upstream remote.",
    )
    p.add_argument(
        "--no-merge-rename",
        action="store_true",
        help="Do not merge --rename-branch into --output.",
    )
    p.add_argument(
        "--commit-message",
        default="chore: rename template files (: -> _) for Windows",
        help="Commit message for the rename commit.",
    )
    return p


def main():
    p = build_parser()
    args = p.parse_args()

    repo_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    print(f"[*] Repo root: {repo_root}")

    if not args.no_fetch:
        ensure_upstream_remote()

    saved = make_windows_branch(
        source=args.source,
        output=args.output,
        repo_root=repo_root,
        message=args.commit_message,
    )

    if not args.no_merge_rename:
        merge_rename_branch(args.rename_branch, args.output)

    print(f"\n[+] Done.  On branch '{args.output}'.")
    print(f"    (Was on '{saved}' before.)")


if __name__ == "__main__":
    main()

