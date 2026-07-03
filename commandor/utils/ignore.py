"""`.commandorignore` file support.

Lets the user exclude files / directories from the agent's reach, similar
to `.gitignore`.  The file is searched upward from the working directory
(so a project-level `.commandorignore` is picked up automatically); the
fallback is `~/.commandor/ignore` for global rules.

Syntax (subset of gitignore):

    # comments are allowed
    *.secret
    /build/                 ← anchored to the project root
    secrets/
    **/*.key
    id_rsa                  ← literal name match anywhere in the tree
    !README.secret          ← re-include a previously ignored file

Public API:
    IgnoreMatcher(base_dir=None)
        .matches(rel_path) -> bool
        .is_ignored(abs_path) -> bool
        .filter(paths: list[str]) -> list[str]   # keeps non-ignored paths

Patterns are evaluated with pathspec-style semantics (fnmatch on each
path segment, with ** matching across directories).
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable, Optional


def _parse_patterns(text: str) -> tuple[list[str], list[str]]:
    """Return (ignore_patterns, reinclude_patterns) from .commandorignore text.

    Lines starting with '!' are re-include rules.  Blank lines and lines
    starting with '#' are skipped.
    """
    ignores: list[str] = []
    reincludes: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            reincludes.append(line[1:].strip())
        else:
            ignores.append(line)
    return ignores, reincludes


def _match_one(pattern: str, rel_path: str) -> bool:
    """Return True if *rel_path* matches *pattern* (gitignore-style)."""
    rel_path = rel_path.replace("\\", "/")
    if rel_path.startswith("./"):
        rel_path = rel_path[2:]

    directory_pattern = pattern.endswith("/")

    # Strip trailing slash for directory patterns
    pat = pattern.replace("\\", "/").rstrip("/")

    # Anchored pattern (starts with /) → must match from project root
    anchored = pat.startswith("/")
    if anchored:
        pat = pat[1:]

    if directory_pattern and anchored:
        return fnmatch.fnmatch(rel_path, pat) or rel_path.startswith(f"{pat}/")

    # Direct match (file or directory name)
    if fnmatch.fnmatch(rel_path, pat):
        return True

    # Match against any suffix of the path (for unanchored patterns)
    if not anchored:
        parts = rel_path.split(os.sep)
        for i in range(len(parts)):
            sub = os.sep.join(parts[i:])
            if fnmatch.fnmatch(sub, pat):
                return True

    # Match against any parent directory name (for directory patterns)
    if not anchored:
        for parent in Path(rel_path).parents:
            parent_str = str(parent)
            # Don't match the empty parent (i.e. ".")
            if parent_str and parent_str != ".":
                if fnmatch.fnmatch(parent_str, pat) or fnmatch.fnmatch(
                    os.path.basename(parent_str), pat
                ):
                    return True

    return False


class IgnoreMatcher:
    """Check whether paths are excluded by .commandorignore rules.

    Search order for the rules file:
        1. <base_dir>/.commandorignore
        2. Walk upward from <base_dir> to the filesystem root
        3. ~/.commandor/ignore   (global fallback)
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()
        self._ignores: list[str] = []
        self._reincludes: list[str] = []
        self._source: Optional[Path] = None
        self._load()

    def _load(self) -> None:
        """Find and load the ignore file."""
        candidates: list[Path] = []

        # 1. <base_dir>/.commandorignore
        candidates.append(self._base_dir / ".commandorignore")

        # 2. Walk upward
        cur = self._base_dir
        for _ in range(20):  # cap at 20 levels to avoid infinite loops
            cur = cur.parent
            if cur == cur.parent:
                break
            candidates.append(cur / ".commandorignore")

        # 3. Global fallback
        candidates.append(Path.home() / ".commandor" / "ignore")

        for cand in candidates:
            try:
                if cand.is_file():
                    text = cand.read_text(encoding="utf-8", errors="replace")
                    self._ignores, self._reincludes = _parse_patterns(text)
                    self._source = cand
                    return
            except OSError:
                continue

    @property
    def source(self) -> Optional[Path]:
        """The path of the loaded ignore file, or None if no rules exist."""
        return self._source

    @property
    def pattern_count(self) -> int:
        """Number of active ignore patterns (re-includes not counted)."""
        return len(self._ignores)

    def matches(self, rel_path: str) -> bool:
        """Return True if *rel_path* (relative to the project root) is ignored.

        Re-include rules ('!pattern') override previous ignore rules.
        """
        if not self._ignores:
            return False

        rel_path = rel_path.replace("\\", "/")
        # Strip leading "./"
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]

        # Evaluate patterns in order; re-include toggles the result on.
        # Spec: a path is ignored if the last matching rule is an ignore rule.
        ignored = False
        for pat in self._ignores:
            if _match_one(pat, rel_path):
                ignored = True
        for pat in self._reincludes:
            if _match_one(pat, rel_path):
                ignored = False
        return ignored

    def is_ignored(self, abs_path: str) -> bool:
        """Convenience: check an absolute path."""
        try:
            p = Path(abs_path)
            if p.is_absolute():
                rel = p.relative_to(self._base_dir)
            else:
                rel = p
        except ValueError:
            # Outside base_dir — treat as not ignored
            return False
        return self.matches(str(rel))

    def filter(self, paths: Iterable[str]) -> list[str]:
        """Return only the paths that are NOT ignored."""
        kept: list[str] = []
        for p in paths:
            if not self.is_ignored(p):
                kept.append(p)
        return kept

    def summary(self) -> str:
        """Return a one-line description of the loaded rules (for /status)."""
        if self._source is None:
            return "no .commandorignore loaded"
        return f"{self._source}  ({len(self._ignores)} ignore, {len(self._reincludes)} re-include)"
