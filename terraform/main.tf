
terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  zone = "ru-central1-a"
  cloud_id                 = "b1gdun28gk5uj1a2cirj"
  folder_id                = "b1gtgl0ktbrjt750ihta"
  service_account_key_file = "./key.json"
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


output "yandex_function_start-compute" {
    value = "${yandex_function.start-compute.id}"
}

output "yandex_function_stop-compute" {
    value = "${yandex_function.stop-compute.id}"
}
