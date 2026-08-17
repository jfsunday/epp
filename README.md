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
3. Random: `a random number between 1 and 100`
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

Routes use `slash` for `/` — `slash api slash users` becomes `/api/users`. Responding with a dictionary auto-serializes to JSON. Custom status codes: `Respond with error and status 404.`

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
```

Works on lists of numbers. No external dependencies needed.

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

**Data structures** — Lists and dictionaries extend the original spec with collection types. Adds `Create`, `Remove`, `For each`, `item of`, `the length of`, `the keys of`, `the entry in`, `contains`, and `has the entry`. `Add` is overloaded to append to lists at runtime.

**Webserver** — Built-in HTTP server using Python's `http.server`. Adds `Start a webserver`, `Add route`, `Respond with`, and `Wait for connections`. Dict responses auto-serialize to JSON.

**Database** — Integrated SQLite database. Adds `Open a database`, `Create a table`, `Insert into`, `Select from`, `Update`, `Delete from`, and `Close the database`. No imports needed.

**Math operations** — `the mean of`, `the sum of`, `the min of`, `the max of`, and `the dot product of` work on lists of numbers without external dependencies.

## Requirements

- Python 3.10+ (stdlib only for core language)
- `python3-tk` for visual statements and games (`sudo pacman -S tk` on Arch/Manjaro, `sudo apt install python3-tk` on Debian/Ubuntu)

## Running Tests

```bash
cd ~/Projekte/epp
pytest -v
```
