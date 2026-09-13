"""Tests for template placeholders and the plus operator on text."""

import os

import pytest


@pytest.fixture
def template_file():
    with open("templatetest", "w") as handle:
        handle.write("Hi {{name}}, you are visitor {count} on {{name}} day.")
    yield "templatetest"
    os.remove("templatetest")


class TestPlaceholders:
    def test_double_and_single_braces(self, run, template_file):
        _, out = run("""
Let who be Alice.
Read the file templatetest and store it in page.
Let page be the value of page with placeholder name replaced by the value of who.
Let page be the value of page with placeholder count replaced by 7.
Say the value of page.
""")
        assert out == ["Hi Alice, you are visitor 7 on Alice day."]

    def test_missing_placeholder_leaves_text_alone(self, run):
        _, out = run("""
Let who be Alice.
Let page be hello there.
Let page be the value of page with placeholder name replaced by the value of who.
Say the value of page.
""")
        assert out == ["hello there"]


class TestTextJoining:
    def test_plus_separates_with_a_space(self, run):
        _, out = run("Let a be hello.\nLet b be world.\nSay the value of a plus b.")
        assert out == ["hello world"]

    def test_joined_with_does_not_add_a_space(self, run):
        _, out = run("Let a be hello.\nLet b be world.\nSay the value of a joined with b.")
        assert out == ["helloworld"]
