"""Tests for E++ string operations, type conversion, and timestamps."""

import time


class TestStringOperations:
    def test_lowercase(self, run):
        _, out = run("""
Let word be HELLO.
Say the lowercase of word.
""")
        assert out == ["hello"]

    def test_uppercase(self, run):
        _, out = run("""
Let word be hello.
Say the uppercase of word.
""")
        assert out == ["HELLO"]

    def test_split(self, run):
        _, out = run("""
Let words be hello world.
Let parts be the split of words by o.
Say the length of parts.
""")
        # "hello world" split by "o" → ["hell", " w", "rld"]
        assert out == ["3"]

    def test_substring(self, run):
        _, out = run("""
Let text be Hello World.
Let sub be the substring of text from 1 to 5.
Say the value of sub.
""")
        assert out == ["Hello"]

    def test_position_found(self, run):
        _, out = run("""
Let text be Hello World.
Let pos be the position of World in text.
Say the value of pos.
""")
        assert out == ["7"]

    def test_position_not_found(self, run):
        _, out = run("""
Let text be Hello World.
Let pos be the position of xyz in text.
Say the value of pos.
""")
        assert out == ["0"]

    def test_replace(self, run):
        _, out = run("""
Let text be Hello World.
Let old be World.
Let new be Earth.
Let result be the value of text with old replaced by new.
Say the value of result.
""")
        assert out == ["Hello Earth"]

    def test_joined_with(self, run):
        _, out = run("""
Let first be John.
Let last be Doe.
Say the value of first joined with last.
""")
        assert out == ["JohnDoe"]

    def test_lowercase_in_condition(self, run):
        _, out = run("""
Let answer be HELLO.
Let lower be the lowercase of answer.
Say the value of lower.
""")
        assert out == ["hello"]


class TestTypeConversion:
    def test_number_of_text(self, run):
        _, out = run("""
Let text be 42.
Let num be the number of text.
Say the value of num plus 8.
""")
        assert out == ["50"]

    def test_number_of_invalid(self, run):
        _, out = run("""
Let text be hello.
Let num be the number of text.
Say the value of num.
""")
        assert out == ["0"]

    def test_text_of_number(self, run):
        _, out = run("""
Let score be 100.
Let txt be the text of score.
Say the value of txt.
""")
        assert out == ["100"]


class TestTimestamps:
    def test_current_timestamp(self, run):
        _, out = run("""
Let now be the current timestamp.
Say the value of now.
""")
        ts = float(out[0])
        assert abs(ts - time.time()) < 5

    def test_current_date(self, run):
        _, out = run("""
Let today be the current date.
Say the value of today.
""")
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", out[0])

    def test_current_time(self, run):
        _, out = run("""
Let now be the current time.
Say the value of now.
""")
        import re
        assert re.match(r"\d{2}:\d{2}:\d{2}", out[0])


class TestRandomItem:
    def test_random_item_from_list(self, run):
        _, out = run("""
Create a list called fruits.
Add apple to fruits.
Add banana to fruits.
Add cherry to fruits.
Let picked be a random item from fruits.
Say the value of picked.
""")
        assert out[0] in ("apple", "banana", "cherry")
