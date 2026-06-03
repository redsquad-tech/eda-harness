---
name: implementation-plan-to-testbenches
description: Используй этот skill чтобы последовательно реализовать все testbench groups из testbench_implementation_plan.md
---

# Skill: Implementation Plan to Testbenches

## Назначение

Последовательно реализуй все testbench groups из `testbench_implementation_plan.md`.

За одну итерацию реализуй только одну текущую group, доведи её до рабочего состояния в ngspice, отчитайся пользователю и спроси, продолжать ли следующую group.

## Входные данные

* `verification_plan.md` — DUT contract, requirements, conditions, metrics и pass/fail limits.
* `testbench_implementation_plan.md` — fixture groups, planned files, CSV outputs и implementation order.
* DUT netlist for development/run — user-provided runnable SPICE netlist or generated mock netlist selected in the previous stage.
* Optional model files/includes — use when the selected DUT netlist requires them.

## Выбор текущей group

Определи текущую group по `Implementation Order`.

Если пользователь явно указал group name — реализуй её.

Если group не указана, выбери первую group по order, у которой нет успешного набора planned files, ngspice log и metrics CSV.

Если все groups уже реализованы и проверены, сообщи, что testbench suite complete.

## Что создать за одну итерацию

Для выбранной group создай или обнови только planned files из `testbench_implementation_plan.md`, обычно:

```text
tests/<group_name>.py
tests/<group_name>.sp
tests/<group_name>.control
results/<group_name>_metrics.csv
results/<group_name>_samples.csv / results/<group_name>_waveforms.csv, если запланировано
results/<group_name>.log
```

Каждая group имеет отдельный HDL21 Python-файл. Не делай один общий generator для всех groups.

## HDL21 fixture requirement

`tests/<group_name>.py` должен реально использовать HDL21 для генерации reusable electrical fixture и экспорта `tests/<group_name>.sp`.

Главное правило: exported `tests/<group_name>.sp` должен быть полноценным testbench fixture, а не thin DUT wrapper.

Правила:

* `tests/<group_name>.py` должен генерировать circuit fixture через HDL21 modules/instances/primitives/helpers.
* Exported `tests/<group_name>.sp` должен содержать DUT instance и электрическую обвязку, нужную для этой group: supply/reference/control sources, loads, capacitors, feedback connections, stimulus elements, named nodes и probe points, где они применимы.
* Для OP/DC/static groups fixture обычно должен содержать все static sources, loads, feedback connections и DUT instance.
* Для TRAN/AC/waveform-like groups fixture должен содержать stimulus/source elements, нужные для анализа, например parameterized PULSE/PWL/AC/DC sources, loads/caps и stable probe nodes.
* `.control` не должен быть основным местом, где создаётся circuit topology testbench-а. Не переноси supply/reference/control/stimulus sources в `.control` только потому, что так проще.
* `.control` должен управлять уже созданным fixture: include/source files, `alterparam`/`alter`, `reset`, analysis commands, measurements, derived metrics, pass/fail, `RESULT`/`FAIL`/`SUMMARY` и CSV/waveform exports.
* SPICE fixture экспортируй через HDL21 netlisting/export flow.
* Не заменяй HDL21 генерацию полной ручной генерацией SPICE-текста.
* Не используй HDL21 только как декоративную декларацию port list поверх handwritten fixture.
* Generated SPICE не редактируй вручную.

Raw-SPICE exception:

* Если нужный simulator-specific element плохо выражается чистыми HDL21 primitives, например PULSE/PWL source, behavioral helper, special probe/helper element, Python generator может добавить небольшой documented raw-SPICE fragment в generated `tests/<group_name>.sp`.
* Такой raw-SPICE fragment должен быть минимальным, локальным для fixture и добавляться из `tests/<group_name>.py` при генерации `.sp`.
* Итоговый `tests/<group_name>.sp` всё равно должен содержать полный reusable fixture со stimulus/source elements.
* Не используй raw-SPICE fragments в `.control` как способ описать основную circuit topology.

Перед завершением fixture проверь:

* можно понять electrical setup group-а, открыв `tests/<group_name>.sp`, без чтения measurement loops в `.control`;
* `.sp` содержит sources/stimulus/load/probe elements, если они нужны group-е;
* `.control` не содержит основной набор V/I source declarations, которые должны быть частью reusable fixture;
* `.control` меняет параметры существующих fixture elements, а не создаёт fixture topology заново.

## Ngspice control requirement

`tests/<group_name>.control` содержит simulator-side логику:

* include/source generated SPICE fixture, selected DUT netlist, and required model/includes;
* run matrix, loops, `alterparam`/`alter`, `reset`;
* analysis commands: OP/DC/TRAN/AC/MC;
* measurements and derived metrics;
* pass/fail checks;
* `RESULT` / `FAIL` / `SUMMARY` lines;
* writing metrics CSV and planned samples/waveform CSV.

Python не должен считать physical metrics и pass/fail.

Для metrics CSV можно использовать simulator-side text output. Для waveform/sample data предпочитай `wrdata` или другой simulator-native export.

Не делай отдельные SPICE decks на каждый run/corner/condition.

## Run matrix and coverage rules

Run matrix должна точно соответствовать coverage для текущей group из `testbench_implementation_plan.md` и соответствующих строк `Acceptance Test Matrix` в `verification_plan.md`.

Правила:

* сначала определи concrete verification-plan items, которые покрывает текущая group;
* для каждого item бери его `Test Condition / Stimulus`, `Condition Coverage`, measurement method и acceptance criteria из `verification_plan.md`;
* `Operating Conditions` и `Presets` из `verification_plan.md` используй как источник значений для тех presets/runs, которые указаны в test matrix;
* не добавляй coverage сверх указанного в test matrix;
* не удаляй coverage, если он явно указан в test matrix, даже если он кажется избыточным для mock DUT;
* если verification plan задаёт nominal-only run, делай nominal-only run;
* если verification plan задаёт sweep по одной группе условий, меняй только эту группу, остальные условия оставляй nominal/fixed;
* если verification plan задаёт full-combination coverage, делай full combination;
* если implementation plan и verification plan расходятся по coverage, используй verification plan как источник истины и укажи assumption/blocker;
* expected run count должен быть рассчитан до написания `.control` и должен совпасть с `SUMMARY runs=<n>`.

## Requirement-specific setup rules

Fixture group может объединять несколько requirements, но это не означает, что они измеряются в одном и том же simulator run.

Перед написанием `.control` составь краткую внутреннюю run table для текущей group:

```text
requirement -> run condition -> measured metric -> source/probe -> limits
```

Правила:

* каждый requirement измеряй только при его собственном `Test Condition / Stimulus` из `verification_plan.md`;
* если два requirements имеют разные fixed bias values, supply values, mode-control values, load values, stimulus или measurement window, они должны быть разными runs/cases внутри одной group;
* общий run можно использовать только если все driven conditions для этих requirements действительно одинаковые;
* нельзя измерять metric для requirement в run-е, который был настроен под другой requirement;
* если в одном OP/TRAN/AC run-е печатаются несколько RESULT rows, каждый RESULT должен соответствовать условиям именно своего requirement;
* `parameters="..."` в RESULT/CSV должен перечислять все requirement-relevant driven values, чтобы было видно, что условие измерения совпало с verification plan;
* если для двух requirements нужен один и тот же fixture, но разные bias cases, используй один fixture и несколько cases/loops в `.control`.

Перед финальным запуском текущей group проверь:

* список фактических `RESULT` rows;
* список параметров в каждом run;
* соответствие фактических runs coverage из verification plan;
* соответствие каждого RESULT своему requirement-specific condition;
* совпадение `SUMMARY runs=<n>` с expected run count.

## Control-file quality rules

Control-файл должен быть компактным, читаемым и поддерживаемым.

Правила:

* если у group больше одного однотипного run, используй `foreach`/loops;
* не копируй большие одинаковые блоки для каждого run, если отличается только параметр;
* одинаковые `alter/reset/analysis/measure/RESULT/FAIL/CSV` patterns должны быть реализованы внутри loop, насколько позволяет ngspice control syntax;
* для разных requirement cases с похожим setup используй общий шаблон и короткие loops/cases, а не длинную копипасту;
* если measurement formula реально отличается, можно разделить на несколько коротких блоков;
* CSV header создавай один раз;
* RESULT/FAIL/log lines и CSV rows должны иметь одинаковый набор полей во всех runs одной group;
* не оставляй dead code, debug-only echoes, временные comments, unused variables или старые альтернативные измерения;
* если loop невозможен из-за ограничения ngspice syntax, явно напиши причину в комментарии control-файла.

Shell-команды внутри `.control` не должны быть основной логикой.

Допустимо:

* простая инициализация/очистка output CSV;
* простая запись строки в CSV, если это стабильнее для ngspice.

Нельзя:

* считать physical metrics в shell;
* делать pass/fail checks в shell;
* создавать сложную файловую архитектуру из `.control`;
* использовать shell как замену ngspice measurements.

## CSV and waveform output rules

Metrics CSV, samples CSV и waveform CSV должны быть пригодны для автоматического чтения report/analysis pipeline.

Правила:

* каждый planned CSV должен быть настоящим comma-separated CSV с consistent delimiter `,`;
* header и data rows должны использовать один и тот же delimiter;
* не смешивай comma-separated header с whitespace-separated data;
* если ngspice `wrdata` пишет whitespace-separated output, либо настрой/построй экспорт так, чтобы итоговый planned файл был корректным CSV, либо используй `.control` text output для записи comma-separated rows;
* waveform/sample CSV должен содержать `run_id` или другой идентификатор run/case, если в один файл попадают данные из нескольких runs;
* если waveform/sample файл содержит данные разных signal modes или swept supplies, добавь колонку `run_id`/`case`/`sweep_target`, чтобы строки можно было однозначно отнести к run condition;
* не аппендь waveform samples из разных runs в один файл без идентификатора run-а;
* если полный waveform слишком большой, сохраняй selected samples/probes или отдельные компактные waveform CSV для representative runs;
* metrics CSV должен иметь schema из `testbench_implementation_plan.md`;
* units должны быть единообразны между log RESULT lines и CSV rows.

## Правила реализации

* Следуй `verification_plan.md` и `testbench_implementation_plan.md`.
* Не меняй group names, planned paths и CSV schema без явной причины.
* Используй только public DUT pins из DUT contract.
* Не используй internal DUT nodes как observability points.
* Не ослабляй acceptance limits ради прохождения.
* Разрабатывай и проверяй на selected runnable DUT netlist from the previous stage. Если был создан mock DUT, используй mock. Если пользователь предоставил runnable real SPICE netlist с нужным public contract, используй его напрямую.
* Output directories должны существовать до записи файлов. Создай их в HDL21 Python source или pre-run step; не делай shell-команды внутри `.control` основной частью архитектуры.

## Ngspice проверка

После создания файлов запусти:

```bash
python tests/<group_name>.py
ngspice -b -o results/<group_name>.log tests/<group_name>.control
```

Если в implementation plan заданы другие paths, используй их.

Исправляй итеративно, пока для текущей group не выполнено:

* HDL21 source запускается без ошибок;
* SPICE fixture сгенерирован через HDL21 flow;
* exported `.sp` является полноценным reusable fixture, а не thin DUT wrapper;
* fixture topology находится в `tests/<group_name>.sp`, а не в `.control`;
* ngspice завершается без fatal parse/runtime errors;
* `.control` выполняет нужный analysis;
* log содержит `RESULT` / `FAIL` / `SUMMARY`;
* metrics CSV создан, не пустой и соответствует schema;
* samples/waveform CSV создан, если он запланирован;
* planned CSV files имеют корректный CSV формат с consistent delimiter;
* waveform/sample CSV содержит run identifier, если в нём есть данные более чем одного run-а;
* DUT/mock run даёт осмысленные измерения для всех metrics текущей group;
* фактическое число runs соответствует coverage из verification plan;
* каждый RESULT row измерен при requirement-specific condition из verification plan;
* control-файл использует loops для однотипных повторяющихся runs или содержит комментарий, почему loop невозможен.

Если ngspice, HDL21, DUT/mock behavior или simulator syntax блокируют проверку, остановись и явно укажи blocker.

## Output contract

Каждый `.control` должен печатать machine-readable lines:

```text
RESULT test=<group_name> requirement=<requirement> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> pass=<0_or_1> limit="<limit>"
FAIL test=<group_name> reason=<reason> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> limit="<limit>"
SUMMARY test=<group_name> runs=<n> fail_count=<n>
```

Metrics CSV должен соответствовать schema из `testbench_implementation_plan.md`.

Не оставляй пустые, NaN или missing metrics без явного blocker.

## Очистка

После успешной проверки текущей group удали временный мусор:

* temporary decks;
* failed-attempt files;
* backup files;
* duplicate logs;
* `__pycache__`;
* лишние raw/binary файлы, если они не являются planned outputs.

Оставь planned source files, generated SPICE fixture, control file, CSV outputs, useful log и нужные samples/waveforms.

## Финальный ответ после каждой group

Ответь кратко:

* какая group реализована;
* какие файлы созданы/обновлены;
* какая ngspice command запускалась;
* какие CSV/log outputs получены;
* expected run count и фактическое число runs;
* DUT/mock pass/fail summary;
* подтверждение, что coverage соответствует verification plan;
* подтверждение, что каждый RESULT соответствует requirement-specific condition, или список assumptions/blockers;
* подтверждение, что exported `.sp` является полноценным fixture, а не thin wrapper;
* подтверждение, что planned CSV/waveform files имеют корректный CSV формат;
* blockers/limitations, если есть;
* какая group следующая;
* спроси пользователя, продолжать ли следующую group.

Не переходи к следующей group без подтверждения пользователя.