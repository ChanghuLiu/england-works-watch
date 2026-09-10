from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import json, logging, os

logger = logging.getLogger("england_works_watch.x402")

_BASE_EIP712_TOKEN_NAMES = {
    "eip155:8453": "USD Coin",   # Base mainnet native USDC name()
    "eip155:84532": "USDC",      # Base Sepolia test USDC name()
}


def eip712_token_identity(network: str) -> tuple[str, str]:
    """Return the exact EIP-712 token domain advertised in x402 requirements.

    Base mainnet Circle USDC reports ``USD Coin`` from the token contract. Base
    Sepolia reports ``USDC``. Mixing the Sepolia name into a mainnet payment
    requirement makes the facilitator reject every authorization with
    ``invalid_exact_evm_token_name_mismatch``.
    """
    override_name = os.getenv("EWW_X402_TOKEN_NAME", "").strip()
    name = override_name or _BASE_EIP712_TOKEN_NAMES.get(network)
    if not name:
        raise RuntimeError(
            f"No EIP-712 token name configured for {network}; set EWW_X402_TOKEN_NAME explicitly"
        )
    version = os.getenv("EWW_X402_TOKEN_VERSION", "2").strip() or "2"
    return name, version


@dataclass(frozen=True)
class PaidToolSpec:
    name:str; price:str; description:str
    input_schema:dict[str,Any]|None=None
    example:dict[str,Any]|None=None


def _default_discovery_contract(spec:PaidToolSpec)->tuple[dict[str,Any],dict[str,Any]|None]:
    if spec.name=='assess_change_impact':
        schema={
            'properties':{
                'payload':{
                    'type':'object',
                    'properties':{
                        'event_type':{'type':'string'},
                        'route':{'type':'string'},
                    },
                    'required':['event_type'],
                    'additionalProperties':True,
                }
            },
            'required':['payload'],
            'additionalProperties':False,
        }
        example={'payload':{'event_type':'unauthorised_absence','route':'skilled_worker','consecutive_working_days':11}}
        return schema,example
    if spec.name=='batch_assess_changes':
        schema={
            'properties':{
                'payload':{
                    'type':'object',
                    'properties':{
                        'changes':{
                            'type':'array','minItems':1,'maxItems':25,
                            'items':{'type':'object','properties':{'event_type':{'type':'string'},'route':{'type':'string'}},'required':['event_type'],'additionalProperties':True},
                        }
                    },
                    'required':['changes'],
                    'additionalProperties':False,
                }
            },
            'required':['payload'],
            'additionalProperties':False,
        }
        example={'payload':{'changes':[{'event_type':'unauthorised_absence','route':'skilled_worker','consecutive_working_days':11}]}}
        return schema,example
    return {'properties':{}},None


def discovery_extensions(spec:PaidToolSpec)->dict[str,Any]:
    """Build the official x402 v2 Bazaar declaration for one paid MCP tool."""
    from x402.extensions.bazaar import DeclareMcpDiscoveryConfig, declare_mcp_discovery_extension
    default_schema,default_example=_default_discovery_contract(spec)
    return declare_mcp_discovery_extension(
        DeclareMcpDiscoveryConfig(
            tool_name=spec.name,
            description=spec.description,
            transport='streamable-http',
            input_schema=spec.input_schema or default_schema,
            example=spec.example or default_example,
        )
    )


class MCP2X402Gate:
    def __init__(self):
        from x402 import x402ResourceServerSync
        from x402.http import FacilitatorConfig, HTTPFacilitatorClientSync
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
        self.network=os.getenv('EWW_X402_NETWORK','eip155:8453').strip(); self.pay_to=os.getenv('EWW_X402_PAY_TO','').strip(); self.facilitator_url=os.getenv('EWW_X402_FACILITATOR_URL','https://facilitator.payai.network').strip()
        self.token_name,self.token_version=eip712_token_identity(self.network)
        if not self.pay_to: raise RuntimeError('EWW_X402_PAY_TO is required when payment enforcement is enabled')
        facilitator=HTTPFacilitatorClientSync(FacilitatorConfig(url=self.facilitator_url)); self.resource_server=x402ResourceServerSync(facilitator); self.resource_server.register(self.network,ExactEvmServerScheme()); self.resource_server.initialize()

        # Non-sensitive payment lifecycle diagnostics. Never log payment payloads,
        # signatures, private keys, seed phrases, or raw MCP arguments.
        def _before_settle(ctx):
            logger.info(
                "x402_settle_start network=%s phase=%s",
                self.network,
                getattr(ctx,'phase','unknown'),
            )

        def _after_settle(ctx):
            result=getattr(ctx,'result',None)
            logger.info(
                "x402_settle_success network=%s phase=%s success=%s transaction=%s",
                self.network,
                getattr(ctx,'phase','unknown'),
                getattr(result,'success',None),
                getattr(result,'transaction','') or '',
            )

        def _settle_failure(ctx):
            error=getattr(ctx,'error',None)
            logger.error(
                "x402_settle_failure network=%s phase=%s error_type=%s error=%s",
                self.network,
                getattr(ctx,'phase','unknown'),
                type(error).__name__ if error is not None else 'unknown',
                str(error) if error is not None else 'unknown',
            )
            return None

        self.resource_server.on_before_settle(_before_settle)
        self.resource_server.on_after_settle(_after_settle)
        self.resource_server.on_settle_failure(_settle_failure)

    def build(self,spec:PaidToolSpec,execute:Callable[[dict[str,Any]],dict[str,Any]]):
        from x402.mcp import ResourceInfo, SyncPaymentWrapperConfig, create_payment_wrapper_sync, MCPToolResult
        from x402.schemas import ResourceConfig
        accepts=self.resource_server.build_payment_requirements(ResourceConfig(scheme='exact',network=self.network,pay_to=self.pay_to,price=spec.price,extra={'name':self.token_name,'version':self.token_version}))
        wrapper=create_payment_wrapper_sync(
            self.resource_server,
            SyncPaymentWrapperConfig(
                accepts=accepts,
                resource=ResourceInfo(
                    url=f'mcp://tool/{spec.name}',
                    description=spec.description,
                    mime_type='application/json',
                    service_name='England Works Watch',
                    tags=['uk','skilled-worker','sponsor','compliance','change-impact'],
                ),
                extensions=discovery_extensions(spec),
            ),
        )
        def business(args,_ctx):
            logger.info("x402_business_start tool=%s",spec.name)
            try:
                payload=execute(args)
            except Exception as error:
                logger.error(
                    "x402_business_failure tool=%s error_type=%s error=%s",
                    spec.name,
                    type(error).__name__,
                    str(error),
                )
                raise
            logger.info(
                "x402_business_success tool=%s status=%s decision_code=%s",
                spec.name,
                payload.get('status','') if isinstance(payload,dict) else '',
                payload.get('decision_code','') if isinstance(payload,dict) else '',
            )
            return MCPToolResult(content=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}],structured_content=payload,is_error=False)
        return wrapper(business)

def meta_to_dict(raw):
    if raw is None:return {}
    if isinstance(raw,dict):return dict(raw)
    dump=getattr(raw,'model_dump',None)
    if callable(dump):
        out=dump(by_alias=True,exclude_none=True); return out if isinstance(out,dict) else {}
    try:return dict(raw)
    except Exception:return {}

def _payment_state(result:Any)->str:
    """Classify x402 lifecycle state, giving settlement responses precedence over challenges."""
    from x402.mcp import MCP_PAYMENT_RESPONSE_META_KEY
    structured=getattr(result,'structured_content',None) or {}
    result_meta=meta_to_dict(getattr(result,'meta',None))
    payment_response=result_meta.get(MCP_PAYMENT_RESPONSE_META_KEY)
    if payment_response is None and isinstance(structured,dict):
        payment_response=structured.get(MCP_PAYMENT_RESPONSE_META_KEY)
    if isinstance(payment_response,dict):
        return 'paid_executed' if bool(payment_response.get('success')) and not bool(getattr(result,'is_error',False)) else 'payment_error'
    if isinstance(structured,dict) and structured.get('x402Version') and structured.get('accepts'):
        return 'challenge'
    return 'payment_error' if bool(getattr(result,'is_error',False)) else 'paid_executed'

def invoke(wrapped,*,tool_name:str,arguments:dict[str,Any],ctx:Any):
    from mcp.types import CallToolResult,TextContent
    from .analytics import record
    rc=getattr(ctx,'request_context',None); meta=meta_to_dict(getattr(rc,'meta',None)); result=wrapped(arguments,{'toolName':tool_name,'_meta':meta}); structured=getattr(result,'structured_content',None) or {}
    payment_state=_payment_state(result)
    record(tool_name,'error' if getattr(result,'is_error',False) else 'ok',billable=True,payment_state=payment_state,meta=meta)
    content=[TextContent(type='text',text=str(b.get('text',''))) for b in (getattr(result,'content',[]) or []) if isinstance(b,dict) and b.get('type')=='text'] or [TextContent(type='text',text='')]
    return CallToolResult(content=content,structured_content=getattr(result,'structured_content',None),is_error=bool(getattr(result,'is_error',False)),_meta=getattr(result,'meta',None) or None)
