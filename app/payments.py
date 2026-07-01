import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models import User, SubscriptionTier, TierType
from app.auth_utils import get_current_user

logger = logging.getLogger("dataprep")

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])

# Initialize Stripe API key
stripe.api_key = settings.stripe_secret_key

# Placeholder ID: replace with your actual Stripe Price ID from the Dashboard
PRO_PRICE_ID = "price_XXXXXXXXXXXXXXXXXXXXXXXX"


@router.post("/create-checkout-session")
async def create_checkout_session(user: User = Depends(get_current_user)):
    """
    Creates a Stripe Checkout session and returns the redirect URL.
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": PRO_PRICE_ID, "quantity": 1}],
            # Metadata allows us to map the Stripe session back to our internal user ID
            metadata={"user_id": str(user.id)},
            # Redirect URLs for the frontend
            success_url="http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:3000/cancel",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        logger.error(f"Stripe session creation failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Payment service unavailable")


@router.post("/webhook")
async def stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None), 
    db: AsyncSession = Depends(get_db)
):
    """
    Stripe webhook endpoint. Processes asynchronous payment events.
    Does not require JWT auth; security is handled via cryptographic signature verification.
    """
    # Webhook verification requires the raw request body
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe signature received")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Handle successful subscription completion
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        user_id = int(session["metadata"]["user_id"])
        customer_id = session["customer"]
        subscription_id = session["subscription"]

        # Fetch the PRO tier record
        tier_query = await db.execute(select(SubscriptionTier).where(SubscriptionTier.name == TierType.PRO))
        pro_tier = tier_query.scalar_one_or_none()

        if pro_tier:
            user_query = await db.execute(select(User).where(User.id == user_id))
            user = user_query.scalar_one()
            
            # Update user subscription status
            user.tier_id = pro_tier.id
            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = subscription_id
            await db.commit()

    # Handle subscription cancellation
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        sub_id = subscription["id"]

        # Locate the user by their Stripe subscription ID
        user_query = await db.execute(select(User).where(User.stripe_subscription_id == sub_id))
        user = user_query.scalar_one_or_none()

        if user:
            tier_query = await db.execute(select(SubscriptionTier).where(SubscriptionTier.name == TierType.BASIC))
            basic_tier = tier_query.scalar_one()
            
            # Revert to the BASIC tier
            user.tier_id = basic_tier.id
            user.stripe_subscription_id = None
            await db.commit()

    # Always return 200 OK to acknowledge receipt of the event
    return {"status": "success"}