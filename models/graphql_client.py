"""
GraphQL client for Stash API communication.
"""
import json
from typing import Any, Dict, Optional

import requests


class GraphQLClient:
    """Client for making GraphQL requests to Stash API."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout

    def call(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for the query
            
        Returns:
            Response data as dictionary
            
        Raises:
            RuntimeError: If HTTP error occurs
        """
        payload = {"query": query, "variables": variables or {}}
        resp = requests.post(self.url, json=payload, headers=self.headers, timeout=self.timeout)
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        return data

    def create_tag(self, tag_name: str) -> str:
        """
        Create tag via tagCreate mutation.
        
        Args:
            tag_name: Name of the tag to create
            
        Returns:
            Tag ID of the created tag
            
        Raises:
            RuntimeError: If tag creation fails
        """
        q = '''
        mutation tagCreate($input: TagCreateInput!) {
          tagCreate(input: $input) {
            id
          }
        }
        '''
        vars = {"input": {"name": tag_name}}
        resp = self.call(q, vars)
        if "data" in resp and resp["data"].get("tagCreate", {}).get("id"):
            return resp["data"]["tagCreate"]["id"]
        else:
            raise RuntimeError("Failed to create tag: " + json.dumps(resp))
