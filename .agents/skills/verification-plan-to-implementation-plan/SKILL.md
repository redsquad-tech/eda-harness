---
name: verification-plan-to-implementation-plan
description: Используй этот skill чтобы создать краткий testbench_implementation_plan.md из verification_plan.md.
---

# Skill: Verification Plan to Testbench Implementation Plan

## Назначение

Создай краткий `testbench_implementation_plan.md` для реализации testbench-ей по `verification_plan.md`.

Implementation plan должен определить минимальный набор будущих testbench groups, их имена, будущие файлы и стабильные CSV outputs.

`testbench_implementation_plan.md` пиши на английском.

## Входные данные

* `verification_plan.md` — основной источник requirements, test matrix, DUT contract, metrics и acceptance criteria.
* Specification — только если нужно уточнить смысл требований.
* Optional DUT/mock netlist — только если нужно уточнить DUT contract.

## Выход

Создай или обнови:

```text
testbench_implementation_plan.md
```

## Структура `testbench_implementation_plan.md`

Используй короткую структуру:

```markdown
# <BLOCK_NAME> Testbench Implementation Plan

## 1. Fixture Groups
## 2. Planned Files and Outputs
## 3. Implementation Order
## 4. Assumptions / Blockers
```

## Fixture Groups

Главная задача — сгруппировать проверки из `verification_plan.md` в минимальное число будущих testbench groups.

Используй таблицу:

```markdown
| Fixture Group | Covers Verification Plan Items | Analysis Type | Grouping Reason |
|---|---|---|---|
| `<group_name>` | `<requirement names / test matrix rows>` | `<OP/DC/TRAN/AC/MC/...>` | `<why these checks belong together>` |
```

Правила группировки:

* Не создавай отдельную group на каждую requirement row.
* Одна group должна покрывать все проверки с общим circuit setup, stimulus, analysis type и observability.
* Derived metrics не получают отдельную group, если считаются из того же waveform/run/analysis.
* Разделяй groups только когда реально отличается setup, stimulus, analysis type или измеряемые public outputs/currents.
* Group name должен быть коротким `snake_case` именем и использоваться как стабильная основа будущих файлов.
* Ссылайся на имена требований и строки test matrix из `verification_plan.md`; не дублируй весь verification plan.

## Planned Files and Outputs

Для каждой group укажи будущие файлы.

Используй таблицу:

```markdown
| Fixture Group | HDL21 Source | Exported SPICE Fixture | Ngspice Control | Metrics CSV | Samples / Waveform CSV |
|---|---|---|---|---|---|
| `<group_name>` | `tests/<group_name>.py` | `tests/<group_name>.sp` | `tests/<group_name>.control` | `results/<group_name>_metrics.csv` | `<planned sample/waveform outputs or none>` |
```

Правила:

* Каждый testbench group реализуется отдельным HDL21 Python-файлом.
* SPICE fixture экспортируется в стабильный путь `tests/<group_name>.sp`.
* Run matrix, measurements, derived metrics и pass/fail checks должны быть в `tests/<group_name>.control`.
* Не планируй отдельные SPICE decks на каждый corner/run/condition.
* Sweep/run logic должна жить в `.control` через simulator-side loops, `alterparam`, `reset` и analysis commands.
* Python-файл нужен для генерации circuit fixture, а не для расчёта физических метрик.
* Если group не требует waveform/sample export, в последней колонке пиши `none`.
* Если group имеет analysis type `TRAN`, `AC`, `noise`, `stability`, `PSRR`, transient response, frequency response или другой waveform-like/probe-based analysis, обязательно планируй waveform/probe artifact для отчёта: `results/<group_name>_waveforms.csv`.
* `results/<group_name>_samples.csv` может быть только дополнительным artifact для compact sample/crossing/sweep/debug points. Не используй samples CSV как замену waveform/probe CSV для TRAN/AC/waveform-like groups.
* Если group требует и компактные sample points, и waveform/probe evidence, укажи оба файла через `<br>` или `;`, например `results/<group_name>_samples.csv; results/<group_name>_waveforms.csv`.
* Если для TRAN/AC/waveform-like group невозможно сохранить waveform/probe CSV, укажи это как blocker. Не планируй только samples CSV вместо waveform CSV.
* Waveform/probe artifacts должны быть запланированы как обычные outputs соответствующей testbench group, чтобы следующий implementation step создал их вместе с metrics/log outputs.

## CSV Outputs

Implementation plan должен зафиксировать только данные, нужные для будущего отчёта и анализа.

Минимальный metrics CSV:

```csv
test_name,requirement,run_id,parameters,metric,value,unit,limit_min,limit_max,pass,fail_reason,source_log
```

Назначение:

* `results/<group_name>_metrics.csv` — один или несколько rows с итоговыми измеренными метриками и pass/fail.
* `results/<group_name>_samples.csv` — sweep/MC/sample/crossing points, если нужны для анализа или debugging.
* `results/<group_name>_waveforms.csv` — стандартный waveform/probe output для TRAN/AC/waveform-like groups. Планируй именно этот stable path независимо от того, просил ли пользователь графики явно.

Правила для sample/waveform outputs:

* Metrics CSV обязателен для каждой group.
* Для OP/DC-only groups обычно достаточно metrics CSV; samples/waveforms можно указать как `none`.
* Для TRAN groups всегда планируй `results/<group_name>_waveforms.csv` как стандартный output с time axis and measured public/probe signals.
* Для AC/frequency-response groups всегда планируй `results/<group_name>_waveforms.csv` с frequency axis and measured signals.
* `results/<group_name>_samples.csv` не заменяет waveform CSV. Он используется только как дополнительный compact evidence/debug artifact.
* Waveform CSV должен иметь run/case identifier, если в один файл попадают данные нескольких runs, например `run_id`, `case` или `sweep_target`.
* Sample CSV должен иметь run/case identifier, если содержит данные нескольких runs.
* Не смешивай metrics, samples и waveforms в один файл.
* Не добавляй PDF/report-specific aggregation в implementation plan. Report skill later reads the stable CSV files.

## Implementation Order

Укажи порядок будущей реализации groups.

Предпочтительный порядок:

1. OP/DC groups;
2. transient groups;
3. AC/stability groups;
4. statistical/Monte Carlo groups, если они есть.

Для каждой итерации следующий skill должен реализовывать только одну group и не менять уже выбранные group names, file paths и CSV schema без явной причины.

## Assumptions / Blockers

Кратко укажи только то, что может помешать реализации:

* неизвестный DUT subckt/module contract;
* отсутствующие model/corner names;
* simulator feature limitations;
* непонятный required waveform/sample export;
* неоднозначные требования, которые не были решены в `verification_plan.md`.

Если group является TRAN/AC/waveform-like, но непонятно, какие именно signals сохранять, не оставляй это молча: планируй `results/<group_name>_waveforms.csv` с основными public/probe signals или укажи blocker.

## Финальный чеклист

Перед завершением проверь:

* все requirements из `verification_plan.md` попали в fixture groups;
* groups не раздроблены без причины;
* для каждой group указаны будущие `.py`, `.sp`, `.control` и CSV paths;
* не запланированы per-run SPICE decks;
* measurements/pass-fail запланированы в `.control`;
* CSV outputs имеют стабильные пути;
* TRAN/AC/waveform-like groups имеют planned waveform/probe CSV; если его невозможно создать, это указано как blocker;
* sample/waveform CSV не смешаны с metrics CSV;
* implementation order задан;
* assumptions/blockers кратко указаны.

## Финальный ответ пользователю

Ответь кратко:

* `testbench_implementation_plan.md` создан/обновлён;
* сколько fixture groups получилось;
* какие будущие файлы и CSV outputs запланированы;
* какие groups планируют waveform/sample artifacts;
* есть ли assumptions/blockers.