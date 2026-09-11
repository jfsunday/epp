# E++ — Programming in Plain English

E++ is a programming language whose source code contains **only** English words, digits, commas, and periods — no symbols like `()`, `{}`, `+`, `-`, `=`, `"`, etc. The name nods at C++ ("E" for English).

Every statement is a sentence ending with a period. Blocks are opened with `do the following.` and closed with `End if.` / `End while.` etc. Text is written as bare words — no quotes needed.

## Quick Start

```bash
python -m epp examples/hello.epp
python -m epp examples/factorial.epp
python -m epp examples/quiz.epp
python -m epp examples/jumper.epp
```

## Language Reference

### Variables

```
Let score be 10.
Let name be Sarah.
Let pi be 3 point 14.
Let temperature be negative 5.
Let is ready be yes.
Set score to 20.
```

Variable names can be multiple words (e.g. `is ready`, `question number`). Types are dynamic: **Number**, **Text**, or **Boolean** (`yes` / `no`).

### Arithmetic Shortcuts

```
Add 5 to score.
Subtract 1 from lives.
Multiply result by counter.
Divide total by 2.
```

### Values

Anywhere a value is expected, it is resolved in this order:

1. Numbers: `42`, `3 point 14`, `negative 5`
2. Booleans: `yes`, `no`
3. Random: `a random number between 1 and 100`, `a random decimal between 0 and 1`
4. Expressions: `the value of x plus y minus 1`
5. Everything else: taken as literal text

### Expressions and Operators

Used after `the value of` and inside conditions:

**Arithmetic:** `plus`, `minus`, `times`, `divided by`, `remainder`

**Comparators:**
- `is equal to` / `is not equal to`
- `is greater than` / `is less than`
- `is greater than or equal to` / `is less than or equal to`

**Logic:** `and`, `or`, `not`

```
the value of price plus tax
age is greater than or equal to 18 and has id is equal to yes
the value of counter remainder 3 is equal to 0
```

Evaluation is left to right with no operator precedence.

### Control Flow

```
If age is less than 13, do the following.
    Say child.
Otherwise if age is less than 20, do the following.
    Say teenager.
Otherwise, do the following.
    Say adult.
End if.

While counter is less than 10, do the following.
    Add 1 to counter.
End while.

Repeat 5 times, do the following.
    Say hello.
End repeat.
```

### Functions

```
Define factorial that takes n, do the following.
    If the value of n is less than 2, do the following.
        Return 1.
    End if.
    Let smaller be the value of n minus 1.
    Call factorial with the value of smaller and store the result in sub.
    Return the value of n times sub.
End define.

Call factorial with 6 and store the result in answer.
Say the value of answer.
```

Zero-parameter functions are also supported:
```
Define greet, do the following.
    Say hello world.
End define.

Call greet.
```

### Input and Output

```
Say hello world.
Say the value of score.
Ask for name.
Ask for age with the message How old are you.
```

`Ask` auto-detects whether the input is a number or text.

### Data Structures

**Lists:**
```
Create a list called fruits.
Add apple to fruits.
Add banana to fruits.
Say item 1 of fruits.
Say the length of fruits.
Set item 1 of fruits to cherry.
Remove item 2 from fruits.
Remove apple from fruits.
```

**Dictionaries:**
```
Create a dictionary called vocab.
Set the entry hello in vocab to hallo.
Say the entry hello in vocab.
Say the length of vocab.
Let words be the keys of vocab.
Remove the entry hello from vocab.
```

**Iteration:**
```
For each fruit in fruits,
    Say the value of fruit.
End for each.
```

**Conditions:**
```
If the value of fruits contains apple,
    Say found it.
End if.

If the value of vocab has the entry hello,
    Say has hello.
End if.
```

`Add` works for both lists (`Add item to list.`) and numbers (`Add 5 to score.`) — resolved at runtime based on the variable type.

### Comments

```
Note, this line is ignored by the interpreter.
```

### Visuals — Windows (Tkinter)

```
Open window with title My App.
Set window size to 600 by 400.
Add label Welcome to my app.
Add button with text Click me that calls my function.
Add text box username.
Set title to New Title.
Set background color to #1e1e2e.
Set text color to #cdd6f4.
Set font size to 16.
Clear window.
Shuffle buttons.
Wait for close.
```

All widgets **scale responsively** when the window is resized — fonts, padding, and label wrapping adapt automatically.

Text box values can be read with `the text box <name>`, e.g.:
```
Add text box username.
Add button with text Submit that calls handle submit.

Define handle submit, do the following.
    Say the text box username.
End define.
```

### Visuals — Turtle Graphics

```
Move forward 100 steps.
Move backward 50 steps.
Turn right 90 degrees.
Turn left 45 degrees.
Pen up.
Pen down.
Set pen color to red.
Draw circle with radius 50.
```

### Webserver

```
Start a webserver on port 8080.

Define handle home that takes request,
    Respond with Hello World.
End define.

Define handle api that takes request,
    Create a dictionary called data.
    Set the entry status in data to ok.
    Respond with the value of data.
End define.

Add route GET slash to handle home.
Add route GET slash api to handle api.
Wait for connections.
```

Routes use `slash` for `/` — `slash api slash users` becomes `/api/users`. Use `param name` for path parameters — `slash users slash param id` matches `/users/42`. Responding with a dictionary auto-serializes to JSON. Custom status codes: `Respond with error and status 404.`

**Path & Query Parameters:**
```
Let id be the path parameter id of request.
Let q be the query parameter q of request.
Let body be the body of request.
```

**Content-Type, CORS & Static Files:**
```
Set content type to text slash html.
Enable CORS.
Serve static files from the folder public.
```

### Database (SQLite)

```
Open a database called myapp.
Create a table called users with columns name and age.
Insert into users the values Alice and 30.
Select from users and store in results.
Select from users where name is equal to Alice and store in found.
Update users set age to 31 where name is equal to Alice.
Delete from users where name is equal to Alice.
Close the database.
```

Directly integrated via SQLite — no imports needed. Select returns a list of dictionaries. Supports all comparison operators in WHERE clauses.

### Math Operations

```
Let avg be the mean of scores.
Let total be the sum of scores.
Let smallest be the min of scores.
Let largest be the max of scores.
Let result be the dot product of X and Y.
Let e be the exponential of 1.
Let x be the logarithm of 10.
```

`mean`, `sum`, `min`, `max`, and `dot product` work on lists of numbers. `exponential` computes e^x, `logarithm` computes ln(x). No external dependencies needed.

### File I/O

```
Read the file data and store it in content.
Write the value of result to the file output.
```

### String Operations

```
Let lower be the lowercase of word.
Let upper be the uppercase of word.
Let parts be the split of text by delimiter.
Let sub be the substring of text from 1 to 5.
Let pos be the position of needle in haystack.
Let result be the value of text with old replaced by new.
Let full be the value of first joined with last.
```

`joined with` concatenates without spaces. `the position of` returns 1-based index (0 if not found). `the substring of` uses 1-based inclusive indexing.

### Timestamps

```
Let now be the current timestamp.
Let today be the current date.
Let time now be the current time.
```

### Type Conversion

```
Let num be the number of text.
Let txt be the text of score.
```

### Random

```
Let n be a random number between 1 and 100.
Let r be a random decimal between 0 and 1.
Let picked be a random item from my list.
```

`random number` returns an integer, `random decimal` returns a float.

### GUI Extensions

```
Add dropdown lessons with options Lektion 1, Lektion 2, Lektion 3.
Let selected be the dropdown lessons.
Add table scores with columns Name, Points.
Add row to scores with values Alice and 100.
Clear table scores.
Wait 2 seconds.
Clear text box username.
Show message Success.
Show error Something went wrong.
```

### Games

```
Start a jump and run game.
```

Launches a 2D side-scrolling platformer with:
- Arrow keys / WASD to move, Space to jump
- Procedurally generated levels — every run is unique
- 6 different chunk patterns (flat runs, staircases, floating islands, gaps, zigzags)
- Increasing difficulty over distance
- Score tracking with high score across restarts

## Example Programs

| File | Description |
|---|---|
| `hello.epp` | Simple greeting with user input |
| `factorial.epp` | Recursive factorial with age validation |
| `fizzbuzz.epp` | Classic FizzBuzz using `remainder` |
| `guess_number.epp` | Number guessing game with random + while loop |
| `shopping_list.epp` | String concatenation and repeat loops |
| `draw_square.epp` | Turtle graphics with interactive shape buttons |
| `quiz.epp` | Multi-category quiz game with 30 questions, scoring, and themed UI |
| `jumper.epp` | Procedurally generated 2D jump'n'run game |
| `vocab.epp` | Latin vocabulary trainer using lists and dictionaries |
| `api.epp` | REST API webserver with JSON responses |
| `database.epp` | SQLite database with CRUD operations |

## Spec Deviations

**`remainder` operator** — Extends the original spec with one new arithmetic operator word. It joins `plus`, `minus`, `times`, `divided by` in expressions. This lets programs express modulo without adding any symbols.

**`Start a jump and run game.`** — Built-in game engine not in the original spec. Adds a single new statement type.

**Responsive sizing** — Widget fonts and layout adapt to window size changes. Not specified in the original spec but follows the spirit of usable visual output.

**Data structures** — Lists and dictionaries extend the original spec with collection types. Adds `Create`, `Remove`, `For each`, `item of`, `Set item of`, `the length of`, `the keys of`, `the entry in`, `contains`, and `has the entry`. `Add` is overloaded to append to lists at runtime.

**Webserver** — Built-in HTTP server using Python's `http.server`. Adds `Start a webserver`, `Add route`, `Respond with`, and `Wait for connections`. Dict responses auto-serialize to JSON.

**Database** — Integrated SQLite database. Adds `Open a database`, `Create a table`, `Insert into`, `Select from`, `Update`, `Delete from`, and `Close the database`. No imports needed.

**Math operations** — `the mean of`, `the sum of`, `the min of`, `the max of`, `the dot product of`, `the exponential of`, and `the logarithm of` for numeric computation without external dependencies.

**File I/O** — `Read the file` and `Write to the file` for basic text file operations.

**String operations** — `the lowercase of`, `the uppercase of`, `the split of`, `the substring of`, `the position of`, `joined with`, and `with X replaced by Y` for text manipulation.

**Timestamps** — `the current timestamp`, `the current date`, `the current time` for date/time access.

**Type conversion** — `the number of` and `the text of` for converting between types.

**Webserver extensions** — Path parameters (`param name`), query parameters, request body access, `Set content type`, `Enable CORS`, `Serve static files` for building full web applications.

**GUI extensions** — Dropdowns, tables, `Wait N seconds`, `Clear text box`, `Show message`, `Show error` for richer desktop applications.

**Random decimals** — `a random decimal between X and Y` for floating-point random numbers (the original `a random number between` returns integers only).

## Requirements

- Python 3.10+ (stdlib only for core language)
- `python3-tk` for visual statements and games (`sudo pacman -S tk` on Arch/Manjaro, `sudo apt install python3-tk` on Debian/Ubuntu)

## Running Tests

```bash
cd ~/Projekte/epp
pytest -v
```
