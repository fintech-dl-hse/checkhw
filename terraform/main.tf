
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
  cloud_id                 = "b1g6j1ocst8nojcl9njp"
  folder_id                = "b1ggdqd3303e40vlujo0"
  service_account_key_file = "./key.json"
}

resource "yandex_compute_instance" "runner-hse" {
  name        = "runner-hse"
  zone        = "ru-central1-b"

  resources {
    cores  = 4
    memory = 8
  }

  boot_disk {
    initialize_params {
      image_id = "fd8emvfmfoaordspe1jr"
      size = 15
    }
  }

  network_interface {
    subnet_id = "e2l7f1j7epi5kckmobpk"
    nat = true
  }

  metadata = {
    user-data = "${file("./metadata.yaml")}"
    ssh-keys = "dtarasov:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFVHTsCNTaI9oVuNKDDtdSVSTN8Csu337MYObrS+7v8w mrsndmn46@gmail.com"
  }
}

resource "yandex_function" "create-compute" {
    name               = "create-compute"
    description        = "Test function to create compute instance"
    user_hash          = "v0.0.3"
    runtime            = "golang119"
    entrypoint         = "start_compute.StartComputeInstances"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajejgsmrst8g2c9dojfi"
    content {
        zip_filename = "functions/compute.zip"
    }
}

resource "yandex_function" "delete-compute" {
    name               = "delete-compute"
    description        = "Test function to delete compute instance"
    user_hash          = "v0.0.1"
    runtime            = "golang119"
    entrypoint         = "stop_compute.StopComputeInstance"
    memory             = "128"
    execution_timeout  = "60"
    service_account_id = "ajejgsmrst8g2c9dojfi"
    content {
        zip_filename = "functions/compute.zip"
    }
}


output "yandex_function_create-compute" {
    value = "${yandex_function.create-compute.id}"
}

output "yandex_function_delete-compute" {
    value = "${yandex_function.delete-compute.id}"
}
