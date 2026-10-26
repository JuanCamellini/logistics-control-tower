from conftest import AS_OF

from lct.alerts import run_alerts


def test_alert_notifies_only_new_critical_orders(master, tmp_path):
    updated, summary = run_alerts(master, AS_OF, tmp_path)

    assert summary.set_index("carrier")["orders"].to_dict() == {"EXPRESO DELTA": 1, "TRANSPORTES ANDINOS": 1}
    delta_email = (tmp_path / "2026-06-30_EXD.html").read_text(encoding="utf-8")
    assert "26100002" in delta_email          # critical since today
    assert "26100003" not in delta_email      # critical, but already notified
    assert "26100001" not in delta_email      # not critical yet
    for header in ("N° de orden", "Cliente", "Dirección", "Localidad", "Bultos", "Fecha de envío",
                   "Días hábiles transcurridos", "Observaciones"):
        assert header in delta_email

    mailed = updated.set_index("Documento de ventas")["Mail"]
    assert mailed.loc[26100002] and mailed.loc[26100004]
    assert not mailed.loc[26100001]


def test_second_run_sends_nothing(master, tmp_path):
    updated, _ = run_alerts(master, AS_OF, tmp_path / "first")
    _, summary = run_alerts(updated, AS_OF, tmp_path / "second")
    assert summary.empty
