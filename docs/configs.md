## Настройки

Удобно задавать настройки файлом (пример [frontik_dev.cfg.ex](../frontik_dev.cfg.ex)). 
Также можно указывать как параметр запуска (`--port=1234`). 
В случае пересечения, приоритет отдается значению из параметра.

В версиях 8.* и ниже файл настроек исполняется как питон код. 
Не стоит завязываться на это поведение, т.к. в будущем планируется перевести их на env, yaml или что-то подобное.

Единственная необходимая настройка для старта - `app_class` путь к классу приложения (`'my_service.MyApplication'`)

Основные настройки (полный список [options.py](../frontik/options.py)).

| Option name                 | Type    | Default value | Description                                                                              |
|-----------------------------| ------- |---------------|------------------------------------------------------------------------------------------|
| `app_class`                 | `str`   | `None`        | Пусть к классу приложения. (см [Рекомендуемая структура проекта](README.md))             |
| `config`                    | `str`   | `None`        | Путь к конфиг файлу                                                                      |
| `host`                      | `str`   | `'0.0.0.0'`   | Хост для входящих запросов                                                               |
| `port`                      | `int`   | `8000`        | Слушаемый порт                                                                           |
| `stop_timeout`              | `int`   | `3`           | Время перед выключением, в течении которого приложение дорабатывает уже принятые запросы |
| `common_executor_pool_size` | `int`   | `10`          | Количество тредов в дефолтном тредпул экзекьюторе                                        |
| `max_active_handlers`       | `int`   | `100`         | Лимит одновременно обрабатываемых запросов на 1 воркере                                  |
| `workers`                   | `int`   | `1`           | Количество воркер процессов                                                              |
| `init_workers_timeout_sec`  | `int`   | `60`          | Время за которое воркер должен успеть запуститься                                        |
| `reuse_port`                | `bool`  | `True`        | Использовать ли SO_REUSEPORT при присвоении сокета                                       |
| `xheaders  `                | `bool`  | `False`       | Включить ли опцию `xheaders` для Tornado HTTPServer                                      |
| `autoreload`                | `bool`  | `False`       | Перезапускать ли приложение при изменни файлов проекта (хот релоад)                      |
| `dev_mode`                  | `bool`  | `False`       | Флаг разработки приложения (устанавливается в True в source-режиме и при запуске из Tilt |
| `debug`                     | `bool`  | `False`       | Включить дебаг режим (для построения дебаг странички)                                    |
| `debug_login`               | `str`   | `None`        | Дебаг логин для basic authentication (когда `debug=False`)                               |
| `debug_password`            | `str`   | `None`        | Дебаг пароль для basic authentication (когда `debug=False`)                              |
| `validate_request_id`       | `bool`  | `False`       | Валидировать ли входящие request_id (32 hex символа)                                     |

Настройки логирования:

| Option name                                 | Type    | Default value | Description                                                     |
|---------------------------------------------|---------|---------------|-----------------------------------------------------------------|
| `log_level`                                 | `str`   | `info`        | Уровень логирования логгер хендлеров (не логгеров!)             |
| `log_dir`                                   | `str`   | `None`        | Путь лог файлов. Создаст файл хендлер. None - не писать в файлы |
| `log_json`                                  | `bool`  | `True`        | Писать ли логи в json формате                                   |
| `log_text_format`                           | `str`   | see code      | Формат лог записей                                              |
| `stderr_log`                                | `bool`  | `False`       | Писать ли логи в stderr                                         |
| `stderr_format`                             | `str`   | see code      | Формат stderr логов                                             |
| `syslog`                                    | `bool`  | `False`       | Писать ли логи в syslog. Создаст syslog хендлер                 |
| `syslog_host`                               | `str`   | `127.0.0.1`   | Syslog хост                                                     |
| `syslog_port`                               | `int`   | `None`        | Syslog порт                                                     |
| `syslog_tag`                                | `str`   | `''`          | Syslog tag                                                      |
| `suppressed_loggers`                        | `list`  | `[]`          | Список логеров не попадающих в дебаг                            |

Дополнительные интеграции:

| Option name                                 | Type    | Default value | Description                                                             |
|---------------------------------------------|---------|--------------|-------------------------------------------------------------------------|
| `statsd_host`                               | `str`   | `None`       | Хост statsd сервера для метрик                                          |
| `statsd_port`                               | `int`   | `None`       | Порт statsd сервера для метрик                                          |
| `sentry_dsn`                                | `str`   | `None`       | Включить сентри, дсн сервера/проекта                                    |
| `consul_enabled`                            | `bool`  | `True`       | Включить consul: registration, kv-store, upstreams                      |
| `consul_host`                               | `str`   | `127.0.0.1`  | Consul хост                                                             |
| `consul_port`                               | `int`   | `None`       | Consul порт                                                             |    
| `upstreams`                                 | `list`  | `[]`         | Список апстримов в которые ходит сервис                                 |
| `fail_start_on_empty_upstream`              | `bool`  | `True`       | Приложение не стартанет если для какого-то из апстримов не будет адреса |
| `asyncio_task_threshold_sec`                | `float` | `None`       | Мониторить и репортить асинкио таски занимающие большое время           |
| `opentelemetry_enabled`                     | `bool`  | `False`      | Включить ли OpenTelemetry                                               |
| `opentelemetry_collector_url`               | `str`   | `127.0.0.1`  | OpenTelemetry адрес коллектора                                          |
