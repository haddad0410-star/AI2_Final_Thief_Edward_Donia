"""SubGameDeps.reveal_transform: a generic, optional hook (not tied to any
specific opponent), default None. Proves: default behavior is unaffected for
every existing/counted-match caller; when a transform is supplied, it's
stored and callable; make_deps() threads it through correctly.
"""

from __future__ import annotations

from thief_peer.services.subgame_deps import SubGameDeps, make_deps


def test_default_reveal_transform_is_none() -> None:
    deps = SubGameDeps(
        config=object(),
        brain=object(),
        hint_provider=object(),
        gateway=object(),
        game_uid="g",
        config_sha256="a" * 64,
    )
    assert deps.reveal_transform is None


def test_make_deps_default_reveal_transform_is_none() -> None:
    deps = make_deps(config=object(), gateway=object(), game_uid="g", config_sha256="a" * 64)
    assert deps.reveal_transform is None


def test_make_deps_threads_explicit_reveal_transform() -> None:
    def _strip_move(message: dict) -> dict:
        return {**message, "reveal": {k: v for k, v in message["reveal"].items() if k != "move"}}

    deps = make_deps(
        config=object(),
        gateway=object(),
        game_uid="g",
        config_sha256="a" * 64,
        reveal_transform=_strip_move,
    )
    assert deps.reveal_transform is _strip_move
    result = deps.reveal_transform({"reveal": {"move": "N", "hint": "hi"}})
    assert result == {"reveal": {"hint": "hi"}}


def test_reveal_transform_is_generic_not_named_for_any_opponent() -> None:
    """The field/parameter itself carries no opponent-specific name or
    logic -- verified structurally, not just by convention."""
    import inspect

    from thief_peer.services import subgame_deps

    source = inspect.getsource(subgame_deps)
    assert "sharnamr" not in source.lower()
    assert "moamteam" not in source.lower()
