"""Tests for E++ database (SQLite)."""

import os
import pytest
from epp.errors import EppRuntimeError


@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    for f in ("testdb.db", "testdb2.db"):
        if os.path.exists(f):
            os.remove(f)


class TestDatabase:
    def test_create_table_and_insert(self, run):
        interp, out = run("""
Open a database called testdb.
Create a table called users with columns name and age.
Insert into users the values Alice and 30.
Select from users and store in results.
Say the length of results.
Close the database.
""")
        assert out == ["1"]

    def test_select_where(self, run):
        interp, out = run("""
Open a database called testdb.
Create a table called items with columns name and price.
Insert into items the values apple and 3.
Insert into items the values banana and 2.
Insert into items the values cherry and 5.
Select from items where name is equal to banana and store in found.
Say the length of found.
Close the database.
""")
        assert out == ["1"]

    def test_select_returns_dicts(self, run):
        interp, out = run("""
Open a database called testdb.
Create a table called people with columns name and city.
Insert into people the values Bob and Berlin.
Select from people and store in results.
Let first be item 1 of results.
Say the entry name in first.
Say the entry city in first.
Close the database.
""")
        assert out == ["Bob", "Berlin"]

    def test_update(self, run):
        interp, out = run("""
Open a database called testdb.
Create a table called scores with columns name and points.
Insert into scores the values Alice and 10.
Update scores set points to 20 where name is equal to Alice.
Select from scores where name is equal to Alice and store in found.
Let row be item 1 of found.
Say the entry points in row.
Close the database.
""")
        assert out == ["20"]

    def test_delete(self, run):
        interp, out = run("""
Open a database called testdb.
Create a table called items with columns name.
Insert into items the values apple.
Insert into items the values banana.
Delete from items where name is equal to apple.
Select from items and store in remaining.
Say the length of remaining.
Close the database.
""")
        assert out == ["1"]

    def test_no_database_open(self, run):
        with pytest.raises(EppRuntimeError, match="no database is open"):
            run("""
Create a table called users with columns name.
""")

    def test_table_not_exists(self, run):
        with pytest.raises(EppRuntimeError, match="does not exist"):
            run("""
Open a database called testdb.
Insert into missing the values hello.
""")
