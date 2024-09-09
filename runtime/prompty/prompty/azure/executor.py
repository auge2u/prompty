import azure.identity
import importlib.metadata
from typing import Iterator
from openai import AzureOpenAI

from prompty.tracer import Tracer
from ..core import Invoker, InvokerFactory, Prompty, PromptyStream

VERSION = importlib.metadata.version("prompty")


@InvokerFactory.register_executor("azure")
@InvokerFactory.register_executor("azure_openai")
class AzureOpenAIExecutor(Invoker):
    """Azure OpenAI Executor"""

    def __init__(self, prompty: Prompty) -> None:
        super().__init__(prompty)
        self.kwargs = {
            key: value
            for key, value in self.prompty.model.configuration.items()
            if key != "type"
        }

        # no key, use default credentials
        if "api_key" not in self.kwargs:
            # managed identity if client id
            if "client_id" in self.kwargs:
                default_credential = azure.identity.ManagedIdentityCredential(
                    client_id=self.kwargs.pop("client_id"),
                )
            # default credential
            else:
                default_credential = azure.identity.DefaultAzureCredential(
                    exclude_shared_token_cache_credential=True
                )

            self.kwargs["azure_ad_token_provider"] = (
                azure.identity.get_bearer_token_provider(
                    default_credential, "https://cognitiveservices.azure.com/.default"
                )
            )

        self.api = self.prompty.model.api
        self.deployment = self.prompty.model.configuration["azure_deployment"]
        self.parameters = self.prompty.model.parameters

    def invoke(self, data: any) -> any:
        """Invoke the Azure OpenAI API

        Parameters
        ----------
        data : any
            The data to send to the Azure OpenAI API

        Returns
        -------
        any
            The response from the Azure OpenAI API
        """

        with Tracer.start("AzureOpenAI") as trace:
            trace("type", "LLM")
            trace("signature", "AzureOpenAI.ctor")
            trace("description", "Azure OpenAI Constructor")
            trace("inputs", self.kwargs)
            client = AzureOpenAI(
                default_headers={
                    "User-Agent": f"prompty/{VERSION}",
                    "x-ms-useragent": f"prompty/{VERSION}",
                },
                **self.kwargs,
            )
            trace("result", client)

        with Tracer.start("create") as trace:
            trace("type", "LLM")
            trace("description", "Azure OpenAI Client")

            if self.api == "chat":
                trace("signature", "AzureOpenAI.beta.chat.completions.parse")
                args = {
                    "model": self.deployment,
                    "messages": data if isinstance(data, list) else [data],
                    **self.parameters,
                }
                trace("inputs", args)
                response = client.beta.chat.completions.parse(**args)
                trace("result", response)

            elif self.api == "completion":
                trace("signature", "AzureOpenAI.completions.create")
                args = {
                    "prompt": data.item,
                    "model": self.deployment,
                    **self.parameters,
                }
                trace("inputs", args)
                response = client.completions.create(**args)
                trace("result", response)

            elif self.api == "embedding":
                trace("signature", "AzureOpenAI.embeddings.create")
                args = {
                    "input": data if isinstance(data, list) else [data],
                    "model": self.deployment,
                    **self.parameters,
                }
                trace("inputs", args)
                response = client.embeddings.create(**args)
                trace("result", response)

            elif self.api == "image":
                raise NotImplementedError("Azure OpenAI Image API is not implemented yet")

        # stream response
        if isinstance(response, Iterator):
            return PromptyStream("AzureOpenAIExecutor", response)
        else:
            return response
