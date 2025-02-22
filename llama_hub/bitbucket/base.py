"""bitbucket reader"""

from typing import List, Optional

import base64
import os
import requests
from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document


class BitbucketReader(BaseReader):
    """Bitbucket reader.

    Reads the content of files in Bitbucket repositories.

    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        project_key: Optional[str] = None,
        branch: Optional[str] = "refs/heads/develop",
    ) -> None:
        """Initialize with parameters."""
        if os.getenv("BITBUCKET_USERNAME") is None:
            raise ValueError("Could not find a Bitbucket username.")
        if os.getenv("BITBUCKET_API_KEY") is None:
            raise ValueError("Could not find a Bitbucket api key.")
        if base_url is None:
            raise ValueError("You must provide a base url for Bitbucket.")
        if project_key is None:
            raise ValueError("You must provide a project key for Bitbucket repository.")
        self.base_url = base_url
        self.project_key = project_key
        self.branch = branch

    def get_headers(self):
        username = os.getenv("BITBUCKET_USERNAME")
        api_token = os.getenv("BITBUCKET_API_KEY")
        auth = base64.b64encode(f"{username}:{api_token}".encode()).decode()
        return {"Authorization": f"Basic {auth}"}

    def get_slugs(self) -> List:
        """
        Get slugs of the specific project.
        """
        repos_url = (
            f"{self.base_url}/rest/api/latest/projects/{self.project_key}/repos/"
        )
        headers = self.get_headers()
        slugs = []
        response = requests.get(repos_url, headers=headers)

        if response.status_code == 200:
            repositories = response.json()["values"]
            for repo in repositories:
                repo_slug = repo["slug"]
                slugs.append(repo_slug)
        return slugs

    def load_all_file_paths(self, slug, branch, directory_path="", paths=[]):
        """
        Go inside every file that is present in the repository and get the paths for each file
        """
        content_url = f"{self.base_url}/rest/api/latest/projects/{self.project_key}/repos/{slug}/browse/{directory_path}"

        query_params = {
            "at": branch,
        }
        headers = self.get_headers()
        response = requests.get(content_url, headers=headers, params=query_params)
        children = response.json()["children"]
        for value in children["values"]:
            if value["type"] == "FILE":
                paths.append(
                    {"slug": slug, "path": f'{directory_path}/{value["path"]["name"]}'}
                )
            elif value["type"] == "DIRECTORY":
                self.load_all_file_paths(
                    slug=slug,
                    branch=branch,
                    directory_path=f'{directory_path}/{value["path"]["name"]}',
                    paths=paths,
                )

    def load_text_by_paths(self, slug, file_path, branch) -> List:
        """
        Go inside every file that is present in the repository and get the paths for each file
        """
        content_url = f"{self.base_url}/rest/api/latest/projects/{self.project_key}/repos/{slug}/browse{file_path}"

        query_params = {
            "at": branch,
        }
        headers = self.get_headers()
        response = requests.get(content_url, headers=headers, params=query_params)
        children = response.json()
        return children["lines"]

    def load_text(self, paths) -> List:
        text_dict = []
        for path in paths:
            lines_list = self.load_text_by_paths(
                self.base_url, self.project_key, path["slug"], path["path"], self.branch
            )
            concatenated_string = ""

            for line_dict in lines_list:
                text = line_dict.get("text", "")
                concatenated_string = concatenated_string + " " + text

            text_dict.append(concatenated_string)
        return text_dict

    def load_data(self) -> List[Document]:
        """Return a list of Document made of each file in Bitbucket."""
        slugs = self.get_slugs()
        paths = []
        for slug in slugs:
            self.load_all_file_paths(
                slug=slug, branch=self.branch, directory_path="", paths=paths
            )
        texts = self.load_text(paths)
        return [Document(text=text) for text in texts]
