
zip-functions:
	(rm functions/compute.zip || true) && zip -rj functions/compute.zip functions/compute
	(rm functions/grades.zip || true)  && zip -rj functions/grades.zip functions/grades

validate: zip-functions
	terraform validate

plan: zip-functions
	terraform plan

apply: zip-functions
	terraform apply

destroy: zip-functions
	terraform destroy
