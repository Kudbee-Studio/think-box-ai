terraform {
  required_providers {
    upcloud = {
      source = "upcloudltd/upcloud"
    }
  }
}

variable "upcloud_api_token" {
  type      = string
  sensitive = true
}

variable "kilo_public_key" {
  type    = string
  default = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee"
}

provider "upcloud" {
  username = "api_token"
  password = var.upcloud_api_token
}

# Reference existing GPU server
data "upcloud_server" "gpu" {
  uuid = "002b8e55-1d81-4b3a-aff5-c15b2df0e66f"
}

# Reference existing GPU storage
data "upcloud_storage" "gpu_disk" {
  uuid = "0158d252-660b-4d7b-ab3d-56da207f0ae1"
}

output "gpu_server_state" {
  value = data.upcloud_server.gpu.state
}

output "gpu_server_ip" {
  value = data.upcloud_server.gpu.ip_addresses
}
