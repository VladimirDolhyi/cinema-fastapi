from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import get_current_user_id, get_accounts_email_notificator
from src.database import get_db, User, UserGroupEnum, Movie, UserGroup
from src.database.models.carts import Cart, CartItem, Purchased
from src.notifications import EmailSenderInterface

from src.schemas.carts import CartResponse, CartItemResponse

router = APIRouter()


@router.post("/")
def create_cart(
    movie_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up.")

    purchase = db.query(Purchased).filter_by(user_id=user_id, movie_id=movie_id).first()
    if purchase:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already bought this movie")

    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Movie not found")

    cart = db.query(Cart).filter_by(user_id=user_id).first()

    if not cart:
        cart = Cart(
            user_id=user_id
        )
        db.add(cart)
        db.commit()
        db.refresh(cart)

    existing_item = db.query(CartItem).filter_by(cart_id=cart.id, movie_id=movie_id).first()
    if existing_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Movie is already in the cart.")

    try:
        cart_item = CartItem(
            cart_id=cart.id,
            movie_id=movie_id
        )
        db.add(cart_item)
        db.commit()
        return {
            "message": f"{movie.name} added in cart successfully"
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data"
        )


@router.get("/{cart_id}/", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    user_id: User = Depends(get_current_user_id)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up.")

    if user.group.name == UserGroupEnum.ADMIN or user.id == user_id:
        cart = db.query(Cart).filter(Cart.user_id == user_id).first()

        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found.")

        cart_items = cart.cart_items

        movies_data = [
            CartItemResponse(
                id=item.movie.id,
                title=item.movie.name,
                price=item.movie.price,
                genre=[genre.name for genre in item.movie.genres],
                release_year=item.movie.year
            )
            for item in cart_items if item.movie
        ]

        return CartResponse(id=cart.id, items=movies_data)
    else:
        raise HTTPException(status_code=403, detail="Not authorized to view this cart.")


@router.delete("/{cart_id}/clear/")
def clear_cart(
    db: Session = Depends(get_db),
    user_id: User = Depends(get_current_user_id)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up.")

    cart = db.query(Cart).filter_by(user_id=user_id).first()
    if not cart:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart not found")

    if not cart.cart_items:
        raise HTTPException(status_code=400, detail="Cart is already empty.")

    try:
        for item in cart.cart_items:
            db.delete(item)

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to clear cart")

    return {"detail": "Cart cleared successfully."}


@router.delete("/{cart_id}/{movie_id}/")
def remove_movie_from_cart(
    movie_id: int,
    cart_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up.")

    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Movie not found")

    cart = db.query(Cart).filter_by(user_id=user_id).first()
    if not cart:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart not found")

    cart_item = db.query(CartItem).filter_by(cart_id=cart.id, movie_id=movie_id).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Movie not found in cart")

    try:
        db.delete(cart_item)
        db.commit()

        moderators = db.query(User).join(UserGroup).filter(UserGroup.name == UserGroupEnum.MODERATOR).all()

        for moderator in moderators:
            background_tasks.add_task(
                email_sender.send_remove_movie,
                moderator.email,
                movie.name,
                cart_id
            )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Please try again later."
        )

    return {
        "message": f"{movie.name} removed from cart id {cart.id} successfully"
    }
