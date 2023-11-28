from locust import task, run_single_user, HttpUser, between


class TestUser(HttpUser):

    # Запуск не в дебаге: poetry run locust -H http://127.0.0.1:9400 -f example_app_load.py

    # host for debug
    host = "http://127.0.0.1:9400"

    @task
    def get_page(self):
        self.client.get(f"/dependencies")



if __name__ == "__main__":
    # for debug
    run_single_user(TestUser)
