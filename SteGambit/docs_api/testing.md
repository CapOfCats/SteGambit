# Тестирование

SteGambit покрыт многоуровневой пирамидой тестов:

## Запуск всех тестов

```bash
pytest tests/
```

### Unit-тесты
Изолированные тесты отдельных компонентов: `CryptoEngine`, `SmartSpreader`, `DctProcessor`, `StegoService`, `FormatIdentifier`.

```bash
pytest tests/unit/ -v
```

### Integration-тесты
Тесты с реальным I/O и полной цепочкой компонентов, проверка совместной работы слоёв.

```bash
pytest tests/integration/ -m integration -v
```

### E2E Smoke
Полный пайплайн *encode → сохранение на диск → extract* на каждом поддерживаемом формате контейнера. Быстрая проверка работоспособности системы в целом.

```bash
pytest tests/e2e/ -v
```

### E2E Load (нагрузочные)
Тяжёлые сценарии на больших медиафайлах (проверка потребления памяти и производительности). Скипаются по умолчанию, чтобы не замедлять CI/CD.

```bash
pytest tests/e2e/test_e2e_load.py -m load -v -s
```