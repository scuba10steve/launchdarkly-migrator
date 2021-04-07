import argparse
import launchdarkly_api
from launchdarkly_api.models import Project, FeatureFlags, FeatureFlag, FeatureFlagBody, FeatureFlagStatus, PatchComment, PatchOperation, FeatureFlagConfig
from launchdarkly_api.rest import ApiException




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--api-token", dest="api_token", help="The LaunchDarkly API Key to authenticate with", required=True)
    parser.add_argument("-s", "--source", help="Project to copy flags from", required=False, default="default")
    parser.add_argument("-d", "--destination", help="the destination project to copy flags to", required=True)

    args = parser.parse_args()
    source = args.source
    destination = args.destination

    configuration = launchdarkly_api.Configuration()
    configuration.api_key['Authorization'] = args.api_token

    base_client = launchdarkly_api.ApiClient(configuration)

    projects_client = launchdarkly_api.ProjectsApi(base_client)
    feature_flags_client = launchdarkly_api.FeatureFlagsApi(base_client)
    
    source_project: Project = projects_client.get_project(source)
    destination_project: Project = projects_client.get_project(destination)


    flags: FeatureFlags = feature_flags_client.get_feature_flags(source_project.key, summary=0)

    for flag_item in flags.items:
        flag: FeatureFlag = flag_item

        new_flag = FeatureFlagBody(flag.name, flag.key, flag.description, flag.variations, flag.temporary, flag.tags, defaults=flag.defaults)
        if flag.include_in_snippet: 
            new_flag.include_in_snippet
        else:
            new_flag.client_side_availability = flag.client_side_availability
        
        destination_environments = [environment.key for environment in destination_project.environments]

        print(f"Creating '{new_flag.name}' in project '{destination_project.name}'...")
        try:
            feature_flags_client.get_feature_flag(destination_project.key, new_flag.key)
        except ApiException as api:
            if api.status == 404:
                feature_flags_client.post_feature_flag(destination_project.key, new_flag)

        for env in [environment.key for environment in source_project.environments]:
            if env in destination_environments:
                config: Dict[str, FeatureFlagConfig] = flag.environments
                
                operations: List[PatchOperation] = []

                if config[env].targets:
                    operations.append(PatchOperation("replace", f"/environments/{env}/targets", config[env].targets))

                if config[env].rules:
                    for rule in config[env].rules:
                        rule.id = ""
                        for clause in rule.clauses:
                            clause.id = ""
                    operations.append(PatchOperation("replace", f"/environments/{env}/rules", config[env].rules))

                if config[env].prerequisites:
                    for prerequisite in config[env].prerequisites:
                        prerequisite.id = ""
                        for clause in prerequisite.clauses:
                            clause.id = ""
                    operations.append(PatchOperation("replace", f"/environments/{env}/prerequisites", config[env].prerequisites))
            
                if operations:
                    update = PatchComment(f"updating rules from prior project '{source_project.name}'", operations)
                    print(f"Updating rules for flag '{new_flag.name}' in project '{destination_project.name}'")
                    feature_flags_client.patch_feature_flag(destination_project.key, new_flag.key, update)


if __name__ == "__main__":
    main()
