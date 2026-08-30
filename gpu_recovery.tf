terraform {
  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = "~> 5.0"
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

# Data source: existing GPU server
data "upcloud_server" "gpu" {
  id = "002b8e55-1d81-4b3a-aff5-c15b2df0e66f"
}

# Data source: existing GPU storage
data "upcloud_storage" "gpu_disk" {
  id = "0158d252-660b-4d7b-ab3d-56da207f0ae1"
}

# Try to create a network for the GPU server
resource "upcloud_network" "gpu_public" {
  name   = "gpu-public-network"
  zone   = "fi-hel2"
  router = upcloud_router.gpu_router.id

  ip_network {
    address = "87.58.148.0/22"
    dhcp    = true
    family  = "IPv4"
  }
}

# Create a router for the GPU network
resource "upcloud_router" "gpu_router" {
  name = "gpu-public-router"
}

output "gpu_state" {
  value = data.upcloud_server.gpu.state
}

output "gpu_title" {
  value = data.upcloud_server.gpu.title
}

output "gpu_disk_info" {
  value = {
    id    = data.upcloud_storage.gpu_disk.id
    title = data.upcloud_storage.gpu_disk.title
    size  = data.upcloud_storage.gpu_disk.size
    state = data.upcloud_storage.gpu_disk.state
  }
}
