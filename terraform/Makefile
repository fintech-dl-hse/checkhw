
zip-functions:
	(rm functions/compute.zip || true) && zip -rj functions/compute.zip functions/compute
	(rm functions/grades.zip || true)  && zip -rj functions/grades.zip functions/grades
	(rm functions/github_actions_hook.zip || true)  && zip -rj functions/github_actions_hook.zip functions/github_actions_hook

validate: zip-functions
	terraform validate

plan: zip-functions
	terraform plan

apply: zip-functions
	terraform apply -auto-approve

destroy: zip-functions
	terraform destroy
