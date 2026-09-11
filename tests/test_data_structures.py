"""Tests for E++ lists and dictionaries."""

import pytest
from epp.errors import EppRuntimeError


class TestLists:
    def test_create_and_add(self, run):
        interp, out = run("""
Create a list called fruits.
Add apple to fruits.
Add banana to fruits.
Say the length of fruits.
""")
        assert out == ["2"]

    def test_item_of(self, run):
        interp, out = run("""
Create a list called colors.
Add red to colors.
Add green to colors.
Add blue to colors.
Say item 1 of colors.
Say item 3 of colors.
""")
        assert out == ["red", "blue"]

    def test_item_of_with_variable_index(self, run):
        interp, out = run("""
Create a list called items.
Add first to items.
Add second to items.
Let idx be 2.
Say item the value of idx of items.
""")
        assert out == ["second"]

    def test_remove_item(self, run):
        interp, out = run("""
Create a list called nums.
Add 10 to nums.
Add 20 to nums.
Add 30 to nums.
Remove item 2 from nums.
Say the length of nums.
Say item 1 of nums.
Say item 2 of nums.
""")
        assert out == ["2", "10", "30"]

    def test_remove_value(self, run):
        interp, out = run("""
Create a list called fruits.
Add apple to fruits.
Add banana to fruits.
Add cherry to fruits.
Remove banana from fruits.
Say the length of fruits.
""")
        assert out == ["2"]

    def test_contains(self, run):
        interp, out = run("""
Create a list called animals.
Add cat to animals.
Add dog to animals.
If the value of animals contains cat,
    Say found cat.
End if.
If the value of animals contains fish,
    Say found fish.
Otherwise,
    Say fish not found.
End if.
""")
        assert out == ["found cat", "fish not found"]

    def test_for_each(self, run):
        interp, out = run("""
Create a list called names.
Add Alice to names.
Add Bob to names.
Add Charlie to names.
For each name in names,
    Say the value of name.
End for each.
""")
        assert out == ["Alice", "Bob", "Charlie"]

    def test_out_of_bounds(self, run):
        with pytest.raises(EppRuntimeError, match="out of bounds"):
            run("""
Create a list called empty.
Say item 1 of empty.
""")

    def test_remove_value_not_found(self, run):
        with pytest.raises(EppRuntimeError, match="not found"):
            run("""
Create a list called items.
Add apple to items.
Remove banana from items.
""")

    def test_empty_list_length(self, run):
        interp, out = run("""
Create a list called empty.
Say the length of empty.
""")
        assert out == ["0"]

    def test_say_list(self, run):
        interp, out = run("""
Create a list called nums.
Add 1 to nums.
Add 2 to nums.
Add 3 to nums.
Say the value of nums.
""")
        assert out == ["[1, 2, 3]"]

    def test_add_number_to_list(self, run):
        interp, out = run("""
Create a list called scores.
Add 100 to scores.
Add 200 to scores.
Say item 1 of scores.
""")
        assert out == ["100"]


class TestDicts:
    def test_create_and_set_entry(self, run):
        interp, out = run("""
Create a dictionary called person.
Set the entry name in person to Alice.
Set the entry age in person to 25.
Say the entry name in person.
Say the entry age in person.
""")
        assert out == ["Alice", "25"]

    def test_length_of_dict(self, run):
        interp, out = run("""
Create a dictionary called d.
Set the entry a in d to 1.
Set the entry b in d to 2.
Say the length of d.
""")
        assert out == ["2"]

    def test_keys_of_dict(self, run):
        interp, out = run("""
Create a dictionary called vocab.
Set the entry hello in vocab to hallo.
Set the entry world in vocab to welt.
Say the value of the keys of vocab.
""")
        # Keys returned as a list
        assert out == ["[hello, world]"]

    def test_has_entry(self, run):
        interp, out = run("""
Create a dictionary called d.
Set the entry color in d to red.
If the value of d has the entry color,
    Say has color.
End if.
If the value of d has the entry size,
    Say has size.
Otherwise,
    Say size not found.
End if.
""")
        assert out == ["has color", "size not found"]

    def test_remove_entry(self, run):
        interp, out = run("""
Create a dictionary called d.
Set the entry x in d to 1.
Set the entry y in d to 2.
Remove the entry x from d.
Say the length of d.
""")
        assert out == ["1"]

    def test_remove_entry_not_found(self, run):
        with pytest.raises(EppRuntimeError, match="not found"):
            run("""
Create a dictionary called d.
Remove the entry missing from d.
""")

    def test_entry_not_found(self, run):
        with pytest.raises(EppRuntimeError, match="not found"):
            run("""
Create a dictionary called d.
Set the entry x in d to 1.
Say the entry missing in d.
""")

    def test_overwrite_entry(self, run):
        interp, out = run("""
Create a dictionary called d.
Set the entry key in d to old.
Set the entry key in d to new value.
Say the entry key in d.
""")
        assert out == ["new value"]

    def test_say_dict(self, run):
        interp, out = run("""
Create a dictionary called d.
Set the entry a in d to 1.
Say the value of d.
""")
        assert out == ["{a: 1}"]


class TestForEachWithDict:
    def test_for_each_over_keys(self, run):
        interp, out = run("""
Create a dictionary called vocab.
Set the entry cat in vocab to Katze.
Set the entry dog in vocab to Hund.
Let words be the keys of vocab.
For each word in words,
    Say the value of word.
End for each.
""")
        assert set(out) == {"cat", "dog"}


class TestNestedStructures:
    def test_list_of_numbers_arithmetic(self, run):
        interp, out = run("""
Create a list called scores.
Add 10 to scores.
Add 20 to scores.
Add 30 to scores.
Let total be 0.
For each score in scores,
    Add the value of score to total.
End for each.
Say the value of total.
""")
        assert out == ["60"]

    def test_set_item(self, run):
        _, out = run("""
Create a list called nums.
Add 10 to nums.
Add 20 to nums.
Add 30 to nums.
Set item 2 of nums to 99.
Say item 1 of nums.
Say item 2 of nums.
Say item 3 of nums.
""")
        assert out == ["10", "99", "30"]

    def test_set_item_with_expression(self, run):
        _, out = run("""
Create a list called w.
Add 0 to w.
Add 0 to w.
Let idx be 2.
Set item idx of w to 42.
Say item 1 of w.
Say item 2 of w.
""")
        assert out == ["0", "42"]

    def test_set_item_out_of_bounds(self, run):
        with pytest.raises(EppRuntimeError):
            run("""
Create a list called w.
Add 1 to w.
Set item 5 of w to 99.
""")

    def test_set_item_not_a_list(self, run):
        with pytest.raises(EppRuntimeError):
            run("""
Let x be 5.
Set item 1 of x to 99.
""")

    def test_dict_with_numeric_values(self, run):
        interp, out = run("""
Create a dictionary called prices.
Set the entry apple in prices to 3.
Set the entry banana in prices to 2.
Say the entry apple in prices.
""")
        assert out == ["3"]
