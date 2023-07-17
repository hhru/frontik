from tests.instances import frontik_test_app


def test_convert_returned_by_handler_value():
    response = frontik_test_app.get_page('/handle_return_value_page')
    assert response.status_code == 200
    response_json = response.json()
    assert response_json['int_field'] == 1
    assert response_json['str_field'] == 'ne_int'
