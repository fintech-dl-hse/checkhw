
zip-functions:
	rm functions/compute.zip && zip -rj functions/compute.zip functions/compute

validate: zip-functions
	terraform validate

plan: zip-functions
	terraform plan

apply: zip-functions
	terraform apply

destroy: zip-functions
	terraform destroy
