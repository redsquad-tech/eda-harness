# Как пользоваться агентом для генерации acceptance testbench-ей

Агент генерирует acceptance testbench-и по спецификации блока/схемы: сначала делает планы, затем по одной группе реализует HDL21 fixture, SPICE fixture, `.control`, ngspice run, CSV/log outputs и в конце может собрать отчёт.

## Что установить заранее

Минимально:

- Python-пакеты для EDA flow: `hdl21`, `vlsirtools`;
- `ngspice`;
- PDK/model files, если DUT netlist их требует, например SKY130 ngspice models;

Для отчёта:

- `pandoc`;
- `xelatex` или `lualatex`;
- Python-пакет `matplotlib`;

## Как подготовить входные данные

В папку блока положи:

```text
specification.pdf / specification.md
dut_netlist.sp          # если есть runnable SPICE DUT
```

Если DUT netlist уже запускается в ngspice и имеет нужный public `.subckt`, агент использует его напрямую. Если runnable DUT нет, агент создаст mock DUT для разработки testbench-ей.

## Как запускать работу с агентом

Напиши агенту примерно так:

```text
Я положил спецификацию и netlist устройства в <path>. Сделай тестбенчи для них.
```

Агент должен сначала кратко предложить план работ и дождаться подтверждения.

## Этапы работы

Агент идёт по этапам и после каждого этапа останавливается:

1. Создаёт `verification_plan.md`.
2. Проверяет DUT netlist или создаёт mock DUT.
3. Создаёт `testbench_implementation_plan.md`.
4. Реализует testbench groups по одной:
   - `tests/<group>.py`
   - `tests/<group>.sp`
   - `tests/<group>.control`
   - `results/<group>.log`
   - `results/<group>_metrics.csv`
   - optional `results/<group>_samples.csv`
   - optional `results/<group>_waveforms.csv`
5. После каждой group агент сообщает результат и спрашивает, продолжать ли следующую.
6. После всех groups можно запустить report stage и получить `test_report.md` / `test_report.pdf`.

## Ожидаемая структура результата

```text
<block>/
  verification_plan.md
  testbench_implementation_plan.md
  tests/
    <group>.py
    <group>.sp
    <group>.control
  results/
    <group>.log
    <group>_metrics.csv
    <group>_samples.csv
    <group>_waveforms.csv
    all_metrics.csv
  schematics/              # optional images for report from user
  test_report.md
  test_report.pdf
```
