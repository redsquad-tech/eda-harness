---
name: testbenches-to-cadence
description: Generate a compact Cadence/Virtuoso SKILL export file for one completed ngspice testbench group. Use when converting the current tests group SPICE and control files into a Cadence library cell, Spectre text view, config view, and Maestro setup with TB_* variables, analyses, outputs, specs, PVT corners, native temperature, and $LIB_PATH model files.
---

# Testbenches To Cadence

## Цель

Сгенерировать компактный Cadence/Virtuoso `generate.il` для завершенных ngspice testbench groups.

Работай по одному group за раз. После генерации одного group кратко отчитайся пользователю и спроси, переходить ли к следующему.

Одна итерация = один group. Не продолжай к следующему group без подтверждения пользователя.

Главный принцип: используй `assets/generate.il.template` как каркас, заполняй его под конкретные `tests/<group>.sp`, DUT netlist и test intent, не строя лишний фреймворк вокруг простой задачи.

## Вход

Ожидаемые источники в workspace:

```text
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
original Spectre DUT netlist
```

Workspace - это директория, где лежат эти файлы. Все Cadence artifacts создавай внутри этого workspace.

## Выход

Создавай или обновляй только artifacts текущего group:

```text
cadence_export/groups/<group>/generate.il
cadence_export/generated_support/cadence_dut.scs
cadence_export/generated_support/<group>.scs
cadence_export/<library_name>/
```

`generate.il` должен создать Cadence cell views:

```text
<library>/<cell>/spectre_<group>
<library>/<cell>/config
<library>/<cell>/maestro
```

Имена по умолчанию:

```text
library = <workspace_name>_acceptance_lib или уже принятое project library name
cell = fixture .SUBCKT name, импортируемый через cdsTextTo5x
test name = <group>
spectre view = spectre_<group>
config view = config
maestro view = maestro
```

## Обязательный поток

1. Определи workspace.
2. Выбери один group. Если group явно не указан, выбери первый group из `testbench_implementation_plan.md`, для которого еще нет Cadence export.
3. Найди source files:
   - `tests/<group>.sp`
   - `tests/<group>.control`
   - оригинальный Spectre DUT netlist.
4. Из `tests/<group>.sp` найди fixture `.SUBCKT`, его параметры, источники, нагрузки, DUT instance и наблюдаемые nodes/branches.
5. Из `.control`, `verification_plan.md` и `testbench_implementation_plan.md` извлеки:
   - `TB_*` параметры и nominal values;
   - analysis intent: `dc`, `op`, `tran`, `ac`;
   - measurements/outputs;
   - specs/checks;
   - run cases;
   - process corners;
   - temperature cases.
6. Скопируй `assets/generate.il.template` в `cadence_export/groups/<group>/generate.il`.
7. Замени placeholders на реальные значения.
8. Запусти генератор из workspace:

```bash
virtuoso -nograph -restore cadence_export/groups/<group>/generate.il
```

Если локально работает только другой известный launch mode, например `-nographE`, используй его.

## Правила generator.il

Держи `generate.il` коротким и понятным. Не добавляй лишние логи, helper-функции, диагностику, `verify.il` или status files.

Комментарии должны быть над смысловыми блоками:

```text
Block 1: names and source files
Block 2: Cadence library
Block 3: Cadence DUT support deck
Block 4: importable Spectre/SPICE wrapper
Block 5: Spectre text view import
Block 6: config view
Block 7: Maestro test
Block 8: nominal fixture variables
Block 9: analysis, outputs, and limits
Block 10: corners matrix
Block 11: save the Maestro setup
```

Можно объединять блоки, если так получается проще и чище. Не меняй структуру шаблона без необходимости; меняй ее только если конкретный testbench иначе не импортируется или не открывается в текущей версии Virtuoso.

## DUT Support

Cadence DUT всегда должен быть оригинальный Spectre DUT netlist, а не mock/dev DUT.

Если оригинальный DUT уже имеет reusable subckt с публичными pins, используй его напрямую через `cadence_dut.scs`.

Если оригинальный DUT является top-level Spectre netlist без нужного public subckt, создай в `cadence_dut.scs` минимальную Spectre-обертку:

```spectre
subckt <dut_subckt_name> <public pins>
<original DUT body>
ends <dut_subckt_name>
```

Для flat Spectre/ADE point netlist `cadence_dut.scs` должен быть clean support deck:

```text
simulator lang=spectre
subckt <dut_subckt_name> <public pins>
<device/subckt instance lines only>
ends <dut_subckt_name>
```

Не копируй в clean DUT subckt/support deck:

```text
ADE/service includes such as ade_e.scs
PDK/model includes from the original point netlist
simulatorOptions
analysis statements
info statements
saveOptions
```

PDK/process models должны приходить из Maestro corner Model Files через `$LIB_PATH/<proc>.scs section <proc>`, а не из `cadence_dut.scs`.

При копировании строк, прочитанных через SKILL `gets`, пиши их без добавочного newline:

```lisp
fprintf(out "%s" line)
```

Не используй:

```lisp
fprintf(out "%s\n" line)
```

## Wrapper Deck

Generated wrapper:

```text
cadence_export/generated_support/<group>.scs
```

Форма wrapper:

```spectre
simulator lang=spectre
include "<absolute path>/cadence_export/generated_support/cadence_dut.scs"

simulator lang=spice
<embedded tests/<group>.sp>
simulator lang=spectre
```

Встраивай содержимое `tests/<group>.sp` в wrapper через чтение файла и `fprintf(out "%s" line)`. Так `tests/<group>.sp` остается source of truth, но `.SUBCKT` становится видимым для `cdsTextTo5x`.

Preferred path: сначала попробуй импорт с clean `cadence_dut.scs` включенным в wrapper, как показано выше. Это сохраняет простую схему: fixture и DUT support видны imported Spectre view, а process models остаются corner-level Model Files.

Fallback path: если `cdsTextTo5x` падает именно из-за включения DUT support, не пересобирай fixture вручную и не клади DUT в Model Files. Оставь wrapper fixture-only:

```spectre
simulator lang=spectre
simulator lang=spice
<embedded tests/<group>.sp>
simulator lang=spectre
```

и подключи `cadence_dut.scs` как Maestro test-level Definition File:

```lisp
maeSetEnvOption(
  testName
  ?options list(list("definitionFiles" list(strcat(cwd "/" dutSupport))))
  ?session sess
)
```

Так `cadence_dut.scs` попадет в generated simulator input как обычный include, но не станет corner Model File.

Не включай в Cadence wrapper:

```text
mock_device.sp
tests/<group>.control
.control
.endc
RESULT/SUMMARY echo logic
wrdata/write raw
quit
```

## Maestro Setup

Создавай один Maestro test на fixture group, если analysis/setup действительно один.

Перед пересозданием generated Maestro view удаляй старую generated view, чтобы повторный запуск не копил duplicate tests/outputs:

```lisp
when(ddGetObj(lib cell maestroView)
  ddDeleteObj(ddGetObj(lib cell maestroView))
)
```

Создавай в Maestro:

```text
TB_* design variables at test level
analysis
outputs once per metric
specs/checks once per metric
corners for run cases and PVT matrix
```

Не создавай отдельные tests для process, temperature, supply/reference/ramp/case matrix. Эти измерения должны быть corners.

## Analysis Setup

Переноси analysis intent из `tests/<group>.control`, `verification_plan.md` и `testbench_implementation_plan.md` в Maestro analysis fields. Не достаточно просто создать `TB_*` variables, если сам analysis их не использует.

Для transient groups задавай stop/max step через `maeSetAnalysis` `?options`, т.к. `maeSetAnalysis` принимает analysis fields через `options`, а не отдельные keyword-аргументы:

```lisp
maeSetAnalysis(
  testName "tran"
  ?enable t
  ?options list(
    list("stop" "<stop_time_expr>")
    list("maxstep" "<max_step_expr>")
  )
  ?session sess
)
```

`<stop_time_expr>` и `<max_step_expr>` должны быть выведены из исходного ngspice transient intent. Если stop/step меняются по cases, задай их через corner-level `TB_*` variables и используй эти variables в analysis options.

Пример формы:

```lisp
maeSetVar("TB_TRAN_STOP" "<nominal_stop>" ?typeName "test" ?typeValue list(testName) ?session sess)
maeSetVar("TB_TRAN_MAXSTEP" "<nominal_step>" ?typeName "test" ?typeValue list(testName) ?session sess)
maeSetAnalysis(
  testName "tran"
  ?enable t
  ?options list(
    list("stop" "TB_TRAN_STOP")
    list("maxstep" "TB_TRAN_MAXSTEP")
  )
  ?session sess
)
```

Если fixture already has meaningful timing variables, можно использовать их напрямую вместо добавления новых generic names, например expression over existing `TB_*` variables. Главное, чтобы сохраненный Maestro state и generated simulator input имели non-empty transient stop/maxstep intent.

## Corners

Собирай corner matrix один раз в список `corners`, затем используй этот список для:

```text
maeSetCorner
corner-level TB_* overrides
AXL native temperature
AXL model files
```

Process model setup делай через model object:

```lisp
model = axlPutModel(cornerHandle proc)
axlSetModelFile(model strcat("$LIB_PATH/" proc ".scs"))
axlSetModelSection(model proc)
axlSetModelTest(model testName)
axlSetEnabled(model t)
```

Не проверяй локальное существование `$LIB_PATH/<proc>.scs`. Это symbolic model reference для Cadence/Spectre окружения.

Не добавляй `cadence_dut.scs` как corner model object. Corner Model Files должны содержать только process model references.

Temperature setup делай как native corner temperature:

```lisp
axlPutVar(cornerHandle "temperature" temp)
```

Не используй только design variable `temp`, если нужна строка Temperature в Corners Setup и simulator option `temp`.

## Outputs And Paths

Создавай outputs через форму `maeAddOutput`:

```lisp
maeAddOutput("<name>" testName ?outputType "point" ?expr "<calculator_expr>" ?session sess)
```

Если текущая Virtuoso версия не принимает `?outputType "point"`, можно опустить `?outputType`, но сохрани `?expr`.

Не используй `?outputType "expr"`, пока не проверишь в этой Cadence версии, что output реально сохранился в `active.state` как `outputsCommon/outputList`. Успешный вызов `maeAddOutput` или наличие `maeSetSpec` не доказывает, что output появился в Maestro GUI.

Output expressions должны ссылаться только на реально достижимые nodes/branches imported Cadence top cell.

Выводи paths из текущего `tests/<group>.sp` и фактического Spectre deck, который создается после `cdsTextTo5x`.

Обязательное правило для наших HDL21/ngspice fixtures:

1. Найди fixture `.SUBCKT <fixture_name> ... .ENDS`.
2. Проверь, есть ли после `.ENDS` top-level instance вида:

```spice
X<top_instance_name> <connections...> <fixture_name>
```

3. Если такой instance есть, он является активным simulation top instance. Все output paths к элементам или узлам внутри fixture должны включать его имя:

```lisp
<calculator_function>("/<top_instance_name>/<element_or_node_path>")
```

4. Не используй укороченные paths вида:

```lisp
<calculator_function>("/<element_or_node_path>")
```

если эти elements/nodes находятся внутри fixture `.SUBCKT`, а не на верхнем уровне deck.

Общее правило выбора:

```text
если imported/generated Spectre deck содержит top-level XTB instance:
  output paths должны включать этот XTB instance

если импортируемый Cadence cell является wrapper/top subckt с fixture instance:
  output paths должны включать этот fixture instance

если fixture sources/nodes реально находятся на самом верхнем уровне deck:
  output paths могут начинаться прямо от этих sources/nodes
```

Для токов через источники используй branch path того источника, который реально существует в fixture. Не хардкодь terminal suffix (`/PLUS`, `/MINUS` или другой): добавляй suffix только если он виден в imported/generated design или нужен локальному ADE calculator для этой ветви.

Для напряжений используй public или fixture-level node path, который реально есть в imported design.

Если есть сомнение, открой generated/imported Spectre view или generated input netlist и выбери путь по фактической иерархии. Если `input.scs` только включает imported `spectre.scs`, открой сам imported `spectre.scs` и смотри, есть ли в нем активный top-level `X... <fixture_name>` instance после `.ENDS`. Не придумывай путь по названию group.

## Что Не Делать

Не делай:

```text
ручное редактирование maestro.sdb, active.state и подобных Cadence state files
mock DUT for Cadence
schematic workaround без просьбы пользователя
full Spectre simulation без просьбы пользователя
verify.il
status files
fake PASS status
```

## Ресурс

Основной каркас:

```text
assets/generate.il.template
```

Используй его как стартовую точку. Меняй placeholder sections и group-specific intent. Не изобретай альтернативный Cadence flow, если шаблон подходит.

Если метод из шаблона недоступен в текущей версии Virtuoso, найди ближайший public API-аналог и сохрани ту же архитектуру: Spectre text import, config, one Maestro test, TB_* variables, Maestro analyses/outputs/specs, PVT corners, native temperature, model objects.

Минимальная проверка после запуска текущего group:

```text
generated_support/<group>.scs embeds tests/<group>.sp verbatim or line-for-line
one Maestro test exists
corner count matches expected matrix
Temperature is native corner temperature
corner Model Files contain only $LIB_PATH/<proc>.scs section <proc>
active.state contains outputsCommon/outputList entries for all expected outputs
cadence_dut.scs is included either by wrapper preferred path or definitionFiles fallback
mock_device.sp is absent from Cadence export/netlist
netlist-only input.scs contains cadence_dut.scs and imported fixture view
```

После генерации текущего group остановись. Не создавай следующий group в том же ответе.
