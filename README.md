# E++ — Programming in Plain English

E++ is a programming language whose source code contains only English words, digits, commas, and periods — no symbols like `()`, `{}`, `+`, `-`, `=`, `"`, etc. The name nods at C++ ("E" for English).

## Usage

```bash
python -m epp examples/hello.epp
python -m epp examples/factorial.epp
python -m epp examples/fizzbuzz.epp
```

## Language Overview

```
Let counter be 0.
Repeat 5 times,
    Add 1 to counter.
    Say the value of counter.
End repeat.
```

### Variables
- `Let <name> be <value>.` — create a variable
- `Set <name> to <value>.` — update a variable
- `Add <n> to <name>.` / `Subtract <n> from <name>.`
- `Multiply <name> by <n>.` / `Divide <name> by <n>.`

### Values
- Numbers: `42`, `3 point 14`, `negative 5`
- Booleans: `yes`, `no`
- Text: any words (auto-detected as string)
- Random: `a random number between 1 and 100`
- Expressions: `the value of x plus y minus 1`

### Control Flow
- `If <condition>, ... Otherwise, ... End if.`
- `While <condition>, ... End while.`
- `Repeat <n> times, ... End repeat.`

### Functions
- `Define <name> that takes <params>, ... End define.`
- `Call <name> with <args> and store the result in <var>.`
- `Return <value>.`

### I/O
- `Say <value>.` — print output
- `Ask for <var> with the message <text>.` — read input (auto-detects number vs text)

### Comments
- `Note <anything>.` — ignored at runtime

### Visuals (Tkinter + Turtle)
- `Open window with title <text>.`
- `Add button with text <text> that calls <function>.`
- `Move forward 100 steps.` / `Turn right 90 degrees.`
- `Wait for close.`

## Spec Deviation

**`remainder` operator** — This implementation extends the spec with one new arithmetic operator word: `remainder`. It joins `plus`, `minus`, `times`, `divided by` in expressions, e.g. `the value of counter remainder 3 is equal to 0`. This lets programs express modulo without adding any symbols and keeps FizzBuzz-style examples natural.

## Running Tests

```bash
cd ~/Projekte/epp
pytest -v
```
