## Opamp v3: тесты для разработки

- Добавить `stage2_ac_budget` тест для второго каскада.
  Цель: отдельно валидировать AC-поведение второго каскада как основного gain stage, а не только его DC law и токовый бюджет.
  Нужно проверять gain/current tradeoff второго каскада в standalone bench.

- Добавить `output_driver_budget` тест для драйвера выходного каскада.
  Цель: формализовать pass/fail на блок `vdrv -> vgdrv`.
  Нужно проверять, что output driver ведет себя как driver, а не как лишний gain stage:
  - ограничение на `vdrv -> vgdrv` gain
  - ограничение на ток драйвера
  - проверка, что рабочая точка не ломается.

- Добавить `output_stage_load_sweep_budget` тест для выходного тракта.
  Цель: валидировать standalone output path под spec-like нагрузками.
  Нужно проверить sweep по нагрузке и выходной емкости для `output driver + output stage`, а не только nominal headroom/current profile.

- Добавить block-level acceptance budgets для каскадов.
  Цель: перейти от диагностических probe-only тестов к явным бюджетам по блокам.
  Нужны отдельные лимиты вида:
  - `stage2_sum <= X`
  - `vdrv -> vgdrv gain <= Y`
  - `output small-signal gain >= Z`
  - `headroom/load behavior` в допустимом окне.

- После добавления этих тестов проверить, хватает ли покрытия, чтобы утверждать, что каждый каскад работает по своей роли и не блокирует достижение spec.
