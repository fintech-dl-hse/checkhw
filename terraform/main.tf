
terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  zone = "ru-central1-d"
  cloud_id                 = "b1gdun28gk5uj1a2cirj"
  folder_id                = "b1gtgl0ktbrjt750ihta"
}

resource "yandex_function" "start-compute" {
    name               = "start-compute"
    description        = "Test function to start compute instance"
    user_hash          = "v0.0.12"
    runtime            = "golang119"
    entrypoint         = "start_compute.StartComputeInstances"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "start-compute-gpu" {
    name               = "start-compute-gpu"
    description        = "Test function to start compute instance"
    user_hash          = "v0.0.12"
    runtime            = "golang119"
    entrypoint         = "start_compute.StartComputeInstancesGPU"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "stop-compute" {
    name               = "stop-compute"
    description        = "Test function to stop compute instance"
    user_hash          = "v0.0.12"
    runtime            = "golang119"
    entrypoint         = "stop_compute.StopComputeInstance"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "homeworks-info" {
    name               = "homeworks-info"
    description        = "Get HTML summary grades table"
    user_hash          = "v0.0.1"
    runtime            = "python312"
    entrypoint         = "index.handler_summary"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajeg6pgmfcbnqvosbefc"
    environment = {
        YDB_DATABASE = "/ru-central1/b1gdun28gk5uj1a2cirj/etnis546o87uog4k54km"
        YDB_ENDPOINT = "grpcs://ydb.serverless.yandexcloud.net:2135"
    }
    content {
        zip_filename = "functions/grades.zip"
    }
}

resource "yandex_function" "homeworks-info-detailed" {
    name               = "homeworks-info-detailed"
    description        = "Get HTML detailed grades table"
    user_hash          = "v0.0.1"
    runtime            = "python312"
    entrypoint         = "index.handler_detailed"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajeg6pgmfcbnqvosbefc"
    environment = {
        YDB_DATABASE = "/ru-central1/b1gdun28gk5uj1a2cirj/etnis546o87uog4k54km"
        YDB_ENDPOINT = "grpcs://ydb.serverless.yandexcloud.net:2135"
    }
    content {
        zip_filename = "functions/grades.zip"
    }
}

resource "yandex_function" "handle-github-hook" {
    name               = "handle-github-hook"
    description        = "Save github hook data to YDB"
    user_hash          = "v0.0.1"
    runtime            = "python312"
    entrypoint         = "index.handler"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajeg6pgmfcbnqvosbefc"
    environment = {
        YDB_DATABASE = "/ru-central1/b1gdun28gk5uj1a2cirj/etnis546o87uog4k54km"
        YDB_ENDPOINT = "grpcs://ydb.serverless.yandexcloud.net:2135"
    }
    secrets {
        id                   = "e6q31h455j5s3qkaaalk"
        version_id           = "e6q5c35paanvd6mc8m0h"
        key                  = "HITHUB_WEBHOOK_SECRET_TOKEN"
        environment_variable = "HITHUB_WEBHOOK_SECRET_TOKEN"
    }
    content {
        zip_filename = "functions/github_actions_hook.zip"
    }
}

output "yandex_function_start-compute" {
    value = "${yandex_function.start-compute.id}"
}

output "yandex_function_stop-compute" {
    value = "${yandex_function.stop-compute.id}"
}
