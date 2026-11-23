import json
import socket
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from backend.banxico_client import CURVE_REQUIRED_SERIES, BanxicoClient, BanxicoClientError
from backend.run_banxico_diagnostic import (
    CF300_REQUIRED_TITLES,
    METADATA_BATCH_SIZE,
    METADATA_CANDIDATE_SERIES,
    LONG_TERM_CANDIDATE_SERIES,
    _fetch_candidate_data,
    _summary,
    acquire_cf300_metadata,
    canonicalize_cf300_title,
    diagnose_cf300_metadata,
    diagnose_required_series,
    inspect_cf300_metadata_candidates,
    locate_long_term_cf300_series,
    diagnose_excel_auxiliary_inputs,
)


def _client_raising(error):
    def transport(*_args):
        raise error
    return BanxicoClient("secret-token-never-log", transport=transport)


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (HTTPError("https://private.invalid", 401, "private body", {}, BytesIO(b"token=private")), "BANXICO_HTTP_401", 401),
        (HTTPError("https://private.invalid", 403, "private body", {}, BytesIO(b"token=private")), "BANXICO_HTTP_403", 403),
        (HTTPError("https://private.invalid", 404, "private body", {}, BytesIO(b"token=private")), "BANXICO_HTTP_404", 404),
        (HTTPError("https://private.invalid", 429, "private body", {}, BytesIO(b"token=private")), "BANXICO_HTTP_429", 429),
        (HTTPError("https://private.invalid", 503, "private body", {}, BytesIO(b"token=private")), "BANXICO_HTTP_5XX", 503),
        (TimeoutError("secret-token-never-log"), "BANXICO_TIMEOUT", None),
        (URLError("private-host"), "BANXICO_NETWORK_ERROR", None),
    ],
)
def test_transport_errors_are_sanitized(error, code, status):
    with pytest.raises(BanxicoClientError) as caught:
        _client_raising(error).fetch_series("SF45422", "2026-11-11", "2026-11-11")
    assert caught.value.code == code
    assert caught.value.http_status == status
    assert "secret-token-never-log" not in str(caught.value)
    assert "private" not in str(caught.value)


def test_invalid_json_is_sanitized():
    def invalid_json(*_args):
        raise json.JSONDecodeError("secret", "secret", 0)
    with pytest.raises(BanxicoClientError) as caught:
        BanxicoClient("secret-token-never-log", transport=invalid_json).fetch_series("SF45422", "2026-11-11", "2026-11-11")
    assert caught.value.code == "BANXICO_JSON_INVALIDO"
    assert "secret" not in str(caught.value)


def test_diagnostic_summary_exposes_only_permitted_fields():
    result = _summary("SF45422", "DATOS", payload={"bmx": {"series": [{"idSerie": "SF45422", "datos": [{"fecha": "11/11/2026", "dato": "28"}]}]}})
    assert result == {
        "serie_id": "SF45422", "tipo_consulta": "DATOS", "http_status": 200,
        "respuesta_json_valida": True, "id_serie_devuelto": "SF45422", "numero_observaciones": 1,
        "primera_fecha": "11/11/2026", "primer_dato": "28", "codigo_error_sanitizado": None,
    }


def _payload(serie_id, dato="10"):
    return {"bmx": {"series": [{"idSerie": serie_id, "datos": [{"fecha": "11/11/2026", "dato": dato}]}]}}


def test_per_series_diagnostic_continues_after_normalization_error_and_is_sanitized():
    class Client:
        def fetch_series(self, serie_id, *_args):
            if serie_id == "SF45439":
                return _payload(serie_id, "N/E")
            return _payload(serie_id)

    entries, issues = diagnose_required_series(Client(), "2026-11-11")
    assert len(entries) == len(CURVE_REQUIRED_SERIES)
    invalid = next(item for item in entries if item["serie_id"] == "SF45439")
    later = next(item for item in entries if item["serie_id"] == "SF45423")
    assert invalid["normalizacion_estado"] == "ERROR"
    assert invalid["raw_dato"] == "N/E"
    assert invalid["codigo_error_sanitizado"] == "BANXICO_RESPUESTA_INVALIDA"
    assert later["normalizacion_estado"] == "NORMALIZADA"
    assert issues == ["SERIE_FALTANTE"]
    permitted = {
        "serie_id", "instrumento", "campo", "http_status", "id_serie_devuelto", "raw_fecha", "raw_dato",
        "normalizacion_estado", "fecha_normalizada", "valor_normalizado", "unidad_normalizada", "codigo_error_sanitizado",
    }
    assert all(set(entry) == permitted for entry in entries)
    assert "secret-token-never-log" not in str(entries)


def test_cf300_metadata_diagnostic_matches_canonical_titles_before_comparing_public_values():
    selected_titles = list(CF300_REQUIRED_TITLES)[:2]
    series_by_title = {selected_titles[0]: "SF45427", selected_titles[1]: "SF45449"}

    class Client:
        def _request(self, url):
            ids = url.rsplit("/", 1)[-1].split(",")
            if "/datos/" in url:
                serie_id = url.split("/series/")[1].split("/")[0]
                title = next(name for name, value in series_by_title.items() if value == serie_id)
                return _payload(serie_id, CF300_REQUIRED_TITLES[title][2])
            return {"bmx": {"series": [{
                "idSerie": serie_id,
                "titulo": "Vector de precios de títulos gubernamentales " + next((name for name, value in series_by_title.items() if value == serie_id), "Otra serie"),
                "unidad": "DÍAS",
                "periodicidad": "Diaria",
                "fechaInicio": "01/01/2020",
                "fechaFin": "11/11/2026",
            } for serie_id in ids]}}

    records, errors = acquire_cf300_metadata(Client())
    matches, comparisons = diagnose_cf300_metadata(Client(), "2026-11-11", records)
    assert errors == []
    assert len(matches) == len(selected_titles)
    assert {canonicalize_cf300_title(item["titulo_oficial"]) for item in matches} == set(selected_titles)
    assert all(item["coincide"] for item in comparisons)
    assert all(item["codigo_error_sanitizado"] is None for item in comparisons)
    assert all(set(item) == {"serie_id", "titulo_oficial", "unidad", "periodicidad", "fecha_inicio", "fecha_fin"} for item in matches)


def test_metadata_batching_respects_limit_reuses_response_and_continues_after_failed_batch():
    class Client:
        calls = []

        def _request(self, url):
            ids = tuple(url.rsplit("/", 1)[-1].split(","))
            self.calls.append(ids)
            if ids[0] == "SF45447":
                raise BanxicoClientError("BANXICO_HTTP_400", 400)
            return {"bmx": {"series": [{
                "idSerie": serie_id,
                "titulo": "Título oficial de prueba",
                "unidad": "DÍAS",
                "periodicidad": "Diaria",
                "fechaInicio": "01/01/2020",
                "fechaFin": "11/11/2026",
            } for serie_id in ids]}}

    client = Client()
    records, errors = acquire_cf300_metadata(client)
    entries = inspect_cf300_metadata_candidates(records)
    assert len(client.calls) == 3
    assert all(len(ids) <= METADATA_BATCH_SIZE for ids in client.calls)
    assert sum(len(ids) for ids in client.calls) == len(METADATA_CANDIDATE_SERIES)
    assert errors == [{"lote": 2, "series_solicitadas": 20, "codigo_error_sanitizado": "BANXICO_HTTP_400"}]
    assert len(entries) == len(METADATA_CANDIDATE_SERIES) - 20
    permitted = {"serie_id", "titulo_oficial", "unidad", "periodicidad", "fecha_inicio", "fecha_fin"}
    assert all(set(item) == permitted for item in entries)


def test_title_canonicalization_removes_only_known_prefix():
    title = "Vector de precios de títulos gubernamentales Bonos 7 a 10 años - Precio Sucio"
    assert canonicalize_cf300_title(title) == "Bonos 7 a 10 años - Precio Sucio"
    assert canonicalize_cf300_title("Otro título Bonos 7 a 10 años - Precio Sucio") == "Otro título Bonos 7 a 10 años - Precio Sucio"


def test_candidate_data_query_refuses_ids_outside_diagnostic_range():
    class Client:
        def _request(self, _url):
            raise AssertionError("No debe hacer solicitud")

    with pytest.raises(BanxicoClientError, match="BANXICO_SERIE_NO_AUTORIZADA"):
        _fetch_candidate_data(Client(), "SF99999", "2026-11-11")


def test_long_term_search_stops_after_three_exact_titles_without_old_range_requests():
    targets = {
        "SF45481": ("Bonos 20 a 30 años - Plazo", "10,396.000000"),
        "SF45482": ("Bonos 20 a 30 años - Precio Sucio", "85.852819"),
        "SF45483": ("Bonos 20 a 30 años - Cupón Vigente", "8.000000"),
    }

    class Client:
        metadata_calls = []

        def _request(self, url):
            if "/datos/" in url:
                serie_id = url.split("/series/")[1].split("/")[0]
                return _payload(serie_id, targets[serie_id][1])
            ids = tuple(url.rsplit("/", 1)[-1].split(","))
            self.metadata_calls.append(ids)
            return {"bmx": {"series": [{
                "idSerie": serie_id,
                "titulo": "Vector de precios de títulos gubernamentales " + targets[serie_id][0],
            } for serie_id in ids if serie_id in targets]}}

    client = Client()
    result = locate_long_term_cf300_series(client, "2026-11-11")
    assert result["campos_encontrados"] == 3
    assert result["candidatos_consultados"] == METADATA_BATCH_SIZE
    assert result["lotes_usados"] == 1
    assert result["ultimo_id_revisado"] == "SF45500"
    assert all(item["coincide"] for item in result["coincidencias"])
    assert len(client.metadata_calls) == 1
    assert all(serie_id in LONG_TERM_CANDIDATE_SERIES for batch in client.metadata_calls for serie_id in batch)


def test_long_term_search_continues_after_failed_batch():
    class Client:
        calls = 0

        def _request(self, url):
            if "/datos/" in url:
                return _payload("SF45501", "10,396.000000")
            self.calls += 1
            if self.calls == 1:
                raise BanxicoClientError("BANXICO_HTTP_400", 400)
            return {"bmx": {"series": [{
                "idSerie": "SF45501",
                "titulo": "Vector de precios de títulos gubernamentales Bonos 20 a 30 años - Plazo",
            }]}}

    result = locate_long_term_cf300_series(Client(), "2026-11-11")
    assert result["errores_por_lote"][0]["codigo_error_sanitizado"] == "BANXICO_HTTP_400"
    assert result["lotes_usados"] == 10
    assert result["campos_encontrados"] == 1


def test_excel_auxiliary_diagnostic_is_limited_sanitized_and_calculates_cete_transformation():
    values = {"SF349886": "674", "SF349888": "8.709819", "SF349889": "7.911961", "SF43774": "6.75"}
    class Client:
        def _request(self, url):
            if "/datos/" in url:
                serie_id = url.split("/series/")[1].split("/")[0]
                return _payload(serie_id, values[serie_id])
            ids = url.rsplit("/", 1)[-1].split(",")
            return {"bmx": {"series": [{"idSerie": serie_id, "titulo": f"Título {serie_id}", "unidad": "Por ciento", "periodicidad": "Diaria", "fechaInicio": "01/01/2000", "fechaFin": "11/11/2026"} for serie_id in ids]}}

    result = diagnose_excel_auxiliary_inputs(Client(), "2026-11-11")
    assert result["disponibles"] == 4
    assert result["codigo_error_metadatos"] is None
    assert result["overnight_rate_propuesto"] == pytest.approx(.0675)
    assert result["transformacion_cete_2y"]["rate_182"] == pytest.approx(.077630163677176, abs=5e-9)
    assert all(set(item) == {"serie_id", "fecha", "raw_dato", "normalizable", "codigo_error_sanitizado"} for item in result["observaciones"])
