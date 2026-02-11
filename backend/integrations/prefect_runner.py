"""Prefect dispatch runner."""

import inspect

from prefect.deployments import run_deployment
from prefect.deployments.runner import RunnerDeployment

from constants import (
    EXECUTION_DEPLOYMENT_NAME,
    EXECUTION_FLOW_ENTRYPOINT,
    EXECUTION_FLOW_NAME,
)
from exceptions import ExecutionDispatchError
from settings import prefect_settings


class PrefectExecutionRunner:
    """Dispatches workflow executions to Prefect."""

    async def _ensure_deployment(
        self,
        flow_entrypoint: str,
        deployment_name: str,
    ) -> None:
        """Create deployment if not registered yet.

        Args:
            flow_entrypoint: Flow entrypoint in module format.
            deployment_name: Deployment name.

        Raises:
            ExecutionDispatchError: If deployment creation fails.

        """
        deployment = RunnerDeployment.from_entrypoint(
            entrypoint=flow_entrypoint,
            name=deployment_name,
            work_pool_name=prefect_settings.pool_name,
        )
        apply_result = deployment.apply(work_pool_name=prefect_settings.pool_name)
        if inspect.isawaitable(apply_result):
            await apply_result

    async def dispatch(
        self,
        flow_entrypoint: str,
        flow_name: str,
        deployment_name: str,
        parameters: dict[str, object],
    ) -> str:
        """Start Prefect flow run for arbitrary flow and deployment.

        Args:
            flow_entrypoint: Flow entrypoint in module format.
            flow_name: Flow name.
            deployment_name: Deployment name.
            parameters: Run parameters.

        Returns:
            Prefect flow run ID.

        Raises:
            ExecutionDispatchError: If dispatch fails.

        """
        try:
            await self._ensure_deployment(
                flow_entrypoint=flow_entrypoint,
                deployment_name=deployment_name,
            )
            flow_run_result = run_deployment(
                name=f"{flow_name}/{deployment_name}",
                parameters=parameters,
                timeout=30,
                as_subflow=False,
            )
            flow_run = (
                await flow_run_result
                if inspect.isawaitable(flow_run_result)
                else flow_run_result
            )
        except Exception as exc:
            raise ExecutionDispatchError(
                message=(
                    f"Failed to dispatch flow '{flow_name}' "
                    f"with deployment '{deployment_name}': {exc}"
                )
            ) from exc

        return str(flow_run.id)

    async def dispatch_execution(self, execution_id: int) -> str:
        """Start Prefect flow run for an execution.

        Args:
            execution_id: Execution ID.

        Returns:
            Prefect flow run ID.

        Raises:
            ExecutionDispatchError: If dispatch fails.

        """
        return await self.dispatch(
            flow_entrypoint=EXECUTION_FLOW_ENTRYPOINT,
            flow_name=EXECUTION_FLOW_NAME,
            deployment_name=EXECUTION_DEPLOYMENT_NAME,
            parameters={"execution_id": execution_id},
        )
