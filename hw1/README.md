# HW1. Лексер Funny: regex → НКА → ДКА → минимальный ДКА

Реализация на Python 3.10+ без внешних зависимостей (только стандартная библиотека).

## Быстрый старт

```bash
cd hw1
python3 -m funnylex all         
```

Отдельные команды:

| Команда | Что делает |
|---|---|
| `python3 -m funnylex build` | читает `tokens.spec`, строит НКА → ДКА → min ДКА, пишет файлы в `build/` |
| `python3 -m funnylex test [-v] [файлы...]` | прогоняет `tests/cases.json` через `build/dfa.json`; печатает только упавшие (с `-v` — все), полный список пишет в `build/test_results.txt` |
| `python3 -m funnylex lex FILE` | токенизирует файл (`-` = stdin); `--keep-skip` показывает WS/COMMENT |
| `python3 -m unittest discover -s tests -v` | то же самое в виде unittest |

Общие опции: `--spec PATH` (по умолчанию `tokens.spec`), `--out DIR` (по умолчанию `build`).
Ставятся до имени команды: `python3 -m funnylex --out /tmp/b build`.

## Структура

```
tokens.spec               вход: список регулярных выражений токенов (имя, вид, regex)
funnylex/
  regex.py                парсер regex → AST (|, , +, ?, (), [..], [^..], ., \n \t \r \xHH \d \w \s)
  nfa.py                  загрузка spec, НКА по Томпсону, объединённый НКА
  dfa.py                  классы символов, построение подмножеств, Хопкрофт, проверки
  build.py                пайплайн и экспорт (JSON / CSV / DOT / stats)
  testing.py              прогон тестов из tests/cases.json
  lexer.py                самодостаточный табличный лексер (для T0)
  __main__.py             CLI
tests/
  cases.json              все тесты: match, lex и chars (каждый ASCII-символ)
  test_hw1.py             unittest-обёртка
examples/                 sample.fun (без ошибок), errors.fun (с ошибками)
build/                    генерируется командой build/test
REPORT.md                 отчёт
```

## Формат `tokens.spec`

Одна строка — одно правило: `ИМЯ  ВИД  РЕГУЛЯРНОЕ_ВЫРАЖЕНИЕ`.

 `ВИД`: `token` — обычный токен; `skip` — распознаётся, но выбрасывается (WS, COMMENT);
  `error` — распознаётся, но лексер выдаёт `ERROR` (например, `BAD_INT`).
 Регулярное выражение — остаток строки после второго поля.
 Приоритет — порядок строк: при равной длине совпадения побеждает правило выше
  (поэтому ключевые слова стоят перед `IDENT`).
 Синтаксис regex: литералы, `|`, ``, `+`, `?`, `( )`, `[a-z]`, `[^...]`, `.`,
  `\n \t \r \0 \xHH \d \w \s`, `\` перед спецсимволом. Алфавит — ASCII 0..127.

## Формат тестов (`tests/cases.json`)

Каждый тест — одна строка файла: входная строка и ожидаемый результат.

```json
{"input": "01", "expect": "BAD_INT"}
{"input": "\u00e9", "expect": null, "trap": true}
{"input": "01+1", "tokens": [["ERROR", "01"], ["PLUS", "+"], ["INT", "1"]]}
{"code": 97, "char": "a", "expect": "IDENT", "trap": false}
```

| Раздел | Поля | Что проверяется |
|---|---|---|
| `match` | `input`, `expect`, необязательно `trap` | строка целиком прогоняется через ДКА; `expect` — токен, который принимает автомат, или `null`; `trap` — попал ли прогон в ловушку |
| `lex` | `input`, `tokens` | лексер режет строку на токены (WS и COMMENT выбрасываются); `tokens` — ожидаемый список пар `[тип, лексема]` |
| `chars` | `code`, `char`, `expect`, `trap` | один символ: проверяются и `match`, и `lex`; `expect` — токен или `ERROR` |

В разделе `chars` каждый ASCII-код 0..127 должен встречаться ровно один раз, иначе тест-раннер выдаёт ошибку.

## Выходные файлы (`build/`)

 `dfa.json` — сериализованный минимальный ДКА, формат `funny-dfa/1` (компактно: одна строка
  файла = одно состояние в `transitions`):
  `tokens` (имя, вид, regex, приоритет), `classes.char_to_class` (128 чисел: ASCII-код → класс),
  `classes.non_ascii_class`, `start`, `trap`, `states[i].accept/kind`,
  `transitions[state][class]`.
 `dfa_transitions.csv` — та же таблица переходов для просмотра глазами.
 `dfa.dot` — граф автомата для Graphviz (`dot -Tsvg build/dfa.dot -o dfa.svg`), дуги в ловушку опущены.
 `stats.json` — размеры НКА/ДКА до и после минимизации.
 `test_results.txt` — список всех тестов и их статусы (PASS/FAIL).

## Подключение в лексер проекта (T0)

`funnylex/lexer.py` зависит только от `json` и файла таблицы:

```python
from funnylex.lexer import DFALexer
lx = DFALexer.from_file("build/dfa.json")
for tok in lx.tokenize(source):       # Token(type, lexeme, offset, error)
    ...
```

Лексер работает по правилу максимального мунка; при равной длине выигрывает правило,
стоящее в `tokens.spec` выше. WS/COMMENT (`skip`) выбрасываются, `BAD_INT` (`error`)
и символы, приводящие сразу в ловушку, превращаются в токены `ERROR`, после чего разбор
продолжается. Позиции строка/столбец — в HW2 (сейчас есть только смещение `offset`).

## Изменение набора токенов

Достаточно отредактировать `tokens.spec` (например, добавить `COLON token :` или
`AND token &&`) и выполнить `python3 -m funnylex all`. В `tests/` нужно добавить
тесты на новый токен, а в разделе `chars` поменять ожидание для символа, с которого он
начинается (иначе этот тест справедливо упадёт).
