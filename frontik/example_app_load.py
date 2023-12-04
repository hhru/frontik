from locust import task, run_single_user, HttpUser, between


class TestUser(HttpUser):

    # Запуск не в дебаге: poetry run locust -H http://127.0.0.1:8080 -f example_app_load.py

    # host for debug
    host = "http://0.0.0.0:9400"

    @task
    def get_page(self):
        self.client.get(f"/status")



if __name__ == "__main__":
    # for debug
    run_single_user(TestUser)
