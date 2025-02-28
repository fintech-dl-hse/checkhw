
terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"

  backend "s3" {
    endpoints = {
      s3 = "https://storage.yandexcloud.net"
    }
    bucket = "fintech-dl-hse-terraform-state"
    region = "ru-central1"
    key    = "terraform_state.tfstate"

    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true # Необходимая опция Terraform для версии 1.6.1 и старше.
    skip_s3_checksum            = true # Необходимая опция при описании бэкенда для Terraform версии 1.6.3 и старше.
  }
}

provider "yandex" {
  zone = "ru-central1-d"
  cloud_id                 = "b1gdun28gk5uj1a2cirj"
  folder_id                = "b1gtgl0ktbrjt750ihta"
}

resource "yandex_function" "start-compute-tf" {
    name               = "start-compute-tf"
    description        = "Test function to start compute instance"
    user_hash          = "v0.0.22"
    runtime            = "golang119"
    entrypoint         = "start_compute.StartComputeInstances"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "start-compute-gpu-tf" {
    name               = "start-compute-gpu-tf"
    description        = "Test function to start compute instance"
    user_hash          = "v0.0.22"
    runtime            = "golang119"
    entrypoint         = "start_compute.StartComputeInstancesGPU"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "stop-compute-tf" {
    name               = "stop-compute-tf"
    description        = "Test function to stop compute instance"
    user_hash          = "v0.0.22"
    runtime            = "golang119"
    entrypoint         = "stop_compute.StopComputeInstance"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "homeworks-info-tf" {
    name               = "homeworks-info-tf"
    description        = "Get HTML summary grades table"
    user_hash          = "v0.0.15"
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

resource "yandex_function" "homeworks-info-detailed-tf" {
    name               = "homeworks-info-detailed-tf"
    description        = "Get HTML detailed grades table"
    user_hash          = "v0.0.15"
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

resource "yandex_function" "handle-github-hook-tf" {
    name               = "handle-github-hook-tf"
    description        = "Save github hook data to YDB"
    user_hash          = "v0.0.4"
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


resource "yandex_function" "check-letters-tf" {
    name               = "check-letters-tf"
    description        = "Check letters hw submit"
    user_hash          = "v0.0.13"
    runtime            = "golang119"
    entrypoint         = "letters.Handler"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    mounts {
        name = "fintech-dl-hse-letters-answers"
        mode = "ro"
        object_storage {
            bucket = "fintech-dl-hse-letters-answers"
        }
    }
    content {
        zip_filename = "functions/letters.zip"
    }
}

resource "yandex_function" "giga-review-tf" {
    name               = "giga-review-tf"
    description        = "Giga review"
    user_hash          = "v0.0.8"
    runtime            = "python312"
    entrypoint         = "index.handler"
    memory             = "512"
    execution_timeout  = "300"
    service_account_id = "ajevd0tfv30vuibuhv6v"
    secrets {
        id                   = "e6qcoml5i8pd749m2pi7"
        version_id           = "e6q6fukbt0r6bdh6qege"
        key                  = "TELEGRAM_BOT_TOKEN"
        environment_variable = "TELEGRAM_BOT_TOKEN"
    }
    secrets {
        id                   = "e6qsp6kj884e4tfgvcrq"
        version_id           = "e6qg7466ek0qt8k5o0d0"
        key                  = "GIGACHAT_CREDENTIALS"
        environment_variable = "GIGACHAT_CREDENTIALS"
    }
    secrets {
        id                   = "e6qabpm2adbfjq16919k"
        version_id           = "e6qkeviqvd3jvo1jniju"
        key                  = "TELEGRAM_BOT_WEBHOOK_SECRET_TOKEN"
        environment_variable = "TELEGRAM_BOT_WEBHOOK_SECRET_TOKEN"
    }
    content {
        zip_filename = "functions/giga-review.zip"
    }
}
