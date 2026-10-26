from datetime import date

import pandas as pd
import pytest

from lct import config as cfg
from lct.generate import build_master, read_master, write_master

START, AS_OF = date(2026, 3, 2), date(2026, 5, 29)   # three months


@pytest.fixture(scope="module")
def generated():
    return build_master(seed=7, start=START, as_of=AS_OF)


def test_same_seed_gives_same_master():
    pd.testing.assert_frame_equal(build_master(seed=1, start=START, as_of=AS_OF),
                                  build_master(seed=1, start=START, as_of=AS_OF))


def test_columns_match_the_master_excel(generated):
    assert list(generated.columns) == cfg.MASTER_COLUMNS


def test_monthly_volume_and_carrier_split(generated):
    assert 3 * 230 * 0.85 <= len(generated) <= 3 * 230 * 1.15
    share = generated["PROVEEDOR"].value_counts(normalize=True)
    assert share["EXPRESO DELTA"] == pytest.approx(160 / 230, abs=0.05)
    assert share["TRANSPORTES ANDINOS"] == pytest.approx(60 / 230, abs=0.05)


def test_dates_follow_the_process(generated):
    g = generated
    assert (g["FECHA DE ENVIO"] > g["Fecha documento"]).all()
    picked = g["FECHA EXACTA DE RETIRO"].notna()
    arrived = g["FECHA EXACTA DE LLEGADA A DC"].notna()
    assert (g.loc[picked, "FECHA EXACTA DE RETIRO"] > g.loc[picked, "FECHA DE ENVIO"]).all()
    assert (g.loc[arrived, "FECHA EXACTA DE LLEGADA A DC"] > g.loc[arrived, "FECHA EXACTA DE RETIRO"]).all()
    assert (g.loc[arrived, "FECHA EXACTA DE LLEGADA A DC"] <= pd.Timestamp(AS_OF)).all()


def test_status_matches_the_dates(generated):
    g = generated
    assert g.loc[g["ESTADO"] == cfg.IN_PROGRESS, "FECHA EXACTA DE RETIRO"].isna().all()
    assert g.loc[g["ESTADO"] == cfg.PICKED_UP, "FECHA EXACTA DE RETIRO"].notna().all()
    assert g.loc[g["ESTADO"] == cfg.PICKED_UP, "FECHA EXACTA DE LLEGADA A DC"].isna().all()
    assert g.loc[g["ESTADO"] == cfg.AT_DEPOT, "FECHA EXACTA DE LLEGADA A DC"].notna().all()


def test_only_pending_orders_can_be_critical_or_notified(generated):
    g = generated
    assert not g.loc[~g["ESTADO"].isin(cfg.PENDING_STATUSES), "Es Critica"].any()
    assert not (g["Mail"] & ~g["Es Critica"]).any()


def test_excel_round_trip(generated, tmp_path):
    path = tmp_path / "maestro.xlsx"
    write_master(generated, path)
    back = read_master(path)
    assert list(back.columns) == cfg.MASTER_COLUMNS
    assert len(back) == len(generated)
    assert back["Mail"].tolist() == generated["Mail"].tolist()
    pd.testing.assert_series_equal(back["FECHA DE ENVIO"], generated["FECHA DE ENVIO"], check_dtype=False)
