# Agent Instructions

Твоя задача — генерировать acceptance testbench-и по спецификации блока/схемы.

Когда пользователь просит сделать testbench-и по спецификации, сначала кратко опиши план работ и дождись подтверждения. Не упоминай названия скиллов в плане.

Работай по этапам:

1. Создай `verification_plan.md`
   Используй skill `spec-to-verification-plan`.

2. Подготовь DUT для разработки testbench-ей
   Если пользователь уже дал runnable SPICE/ngspice netlist с нужным public `.subckt` и pin order — используй этот netlist напрямую. Не создавай HDL21 DUT и не создавай mock.
   Если пользователь уже дал подходящий HDL21 DUT/mock и/или SPICE netlist — используй их.
   Если runnable DUT/mock нет — создай mock DUT через skill `spec-to-hdl21-mock-dut`.

3. Создай `testbench_implementation_plan.md`
   Используй skill `verification-plan-to-implementation-plan`.
   План должен задать минимальный набор testbench groups, будущие файлы, stable output paths и порядок реализации.

4. Реализуй testbench groups последовательно
   Используй skill `implementation-plan-to-testbenches`.
   Делай одну group за итерацию: HDL21 fixture → exported SPICE → `.control` → ngspice run → CSV/log outputs → cleanup.
   После каждой group отчитайся и спроси пользователя, продолжать ли следующую.

5. После завершения всех testbench groups создай отчет
   Используй skill `test2report`.
   Сгенерируй `test_report.md` и `test_report.pdf`.

После каждого этапа остановись, кратко отчитайся о результате и спроси пользователя, продолжать ли следующий этап. Не переходи к следующему skill/этапу без подтверждения пользователя.

Общие правила:

* HDL21 используется для генерации circuit fixtures; не подменяй его handwritten SPICE templates.
* DUT не обязан быть написан на HDL21, если пользователь уже дал runnable SPICE/ngspice netlist с правильным public contract.
* Если есть подходящий пользовательский runnable DUT netlist — используй его. Mock DUT создавай только если runnable DUT/mock отсутствует.
* `.control` files отвечают за include выбранного DUT netlist/model files, sweeps, measurements, pass/fail, `RESULT`/`FAIL`/`SUMMARY` и CSV outputs.
* Python не должен считать physical metrics или pass/fail.
* Используй только public DUT pins.
* Не используй internal DUT nodes как acceptance observability points.
* Не ослабляй limits из спецификации.
* Держи структуру файлов минимальной и stable для downstream report generation.
* Если входные документы или netlist противоречат друг другу, зафиксируй assumption/blocker и не угадывай молча.
