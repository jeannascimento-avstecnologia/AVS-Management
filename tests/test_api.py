from fastapi.testclient import TestClient



from src.main import app



client = TestClient(app)





def test_health():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json()["status"] == "ok"





def test_index_html_home_and_flow():

    response = client.get("/")

    assert response.status_code == 200

    text = response.text

    assert "AVS" in text
    assert "/static/logo-avs.png" in text
    assert "brand-logo" in text

    assert "Central de integrações" in text

    assert "Cadastrar Cliente" in text

    assert "Informe o CNPJ" in text

    assert "result-box" in text

    assert "alertCnpj" in text
    assert "registration_status" in text





def test_preview_missing_cnpj():

    response = client.post("/preview", data={})

    assert response.status_code == 400

    assert response.json()["success"] is False

    assert "error" in response.json()





def test_preview_invalid_cnpj_shows_error():

    response = client.post("/preview", data={"cnpj": "000"})

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False

    assert body.get("error")





def test_integrar_missing_cnpj():

    response = client.post("/integrar", json={})

    assert response.status_code == 400





def test_static_logo_served():
    response = client.get("/static/logo-avs.png")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/")


def test_integrar_invalid_cnpj():

    response = client.post(

        "/integrar",

        json={"company": {"cnpj_digits": "000"}, "desk_ids": [1], "technical_group_ids": [1]},

    )

    assert response.status_code == 400


