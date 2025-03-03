from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.config import get_current_user_id
from src.database import get_db, User, UserGroupEnum
from src.database.models.movies import (
    Movie,
    Genre, Director, Star, Comment, AnswerComment, Favorite, Certification, Like, Dislike
)
from src.schemas.movies import (
    MovieListItemSchema,
    MovieListResponseSchema, MovieDetailSchema, MovieCreateSchema, MovieUpdateSchema
)

from src.notifications.emails import EmailSender

router = APIRouter()


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
            "<h3>This endpoint retrieves a paginated list of movies from the database. "
            "Clients can specify the `page` number and the number of items per page using `per_page`. "
            "The response includes details about the movies, total pages, and total items, "
            "along with links to the previous and next pages if applicable.</h3>"
    ),
    responses={
        404: {
            "description": "No movies found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No movies found."}
                }
            },
        }
    }
)
def get_movie_list(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
    year: int | None = Query(None, description="Filter by year"),
    min_imdb: float | None = Query(None, description="Filter by min_imdb"),
    max_imdb: float | None = Query(None, description="Filter by max_imdb"),
    genre: str | None = Query(None, description="Filter by genre name"),
    director: str | None = Query(None, description="Filter by director name"),
    star: str | None = Query(None, description="Filter by star name"),
    search: str | None = Query(None, description="Search by title, description, actor or director"),
    sort_by: str | None = Query(None, description="Sort by 'price', 'year', 'votes'"),
    db: Session = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Fetch a paginated list of movies from the database.

    This function retrieves a paginated list of movies, allowing the client to specify
    the page number and the number of items per page. It calculates the total pages
    and provides links to the previous and next pages when applicable.
    """
    offset = (page - 1) * per_page

    query = db.query(Movie).order_by()

    order_by = Movie.default_order_by()
    if order_by:
        query = query.order_by(*order_by)

    if year:
        query = query.filter(Movie.year == year)
    if min_imdb:
        query = query.filter(Movie.imdb >= min_imdb)
    if max_imdb:
        query = query.filter(Movie.imdb <= max_imdb)
    if director:
        query = query.join(Movie.directors).filter(Director.name.ilike(f"%{director}%"))
    if star:
        query = query.join(Movie.stars).filter(Star.name.ilike(f"%{star}%"))
    if genre:
        query = query.join(Movie.genres).filter(Genre.name.ilike(f"%{genre}%"))

    if search:
        query = (
            query.outerjoin(Movie.directors)
            .outerjoin(Movie.stars)
            .filter(
                or_(
                    Movie.name.ilike(f"%{search}%"),
                    Movie.description.ilike(f"%{search}%"),
                    Director.name.ilike(f"%{search}%"),
                    Star.name.ilike(f"%{search}%"),
                )
            )
        )

    sort_fields = {
        "price": Movie.price,
        "year": Movie.year,
        "votes": Movie.votes,
    }
    if sort_by in sort_fields:
        query = query.order_by(sort_fields[sort_by].desc())

    total_items = query.count()

    movies = query.offset(offset).limit(per_page).all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    movie_list = [
        MovieListItemSchema.model_validate(movie)
        for movie in movies
    ]

    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description=(
            "<h3>Fetch detailed information about a specific movie by its unique ID. "
            "This endpoint retrieves all available details for the movie, such as "
            "its name, genre, crew, budget, and revenue. If the movie with the given "
            "ID is not found, a 404 error will be returned.</h3>"
    ),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    }
)
def get_movie_by_id(
    movie_id: int,
    db: Session = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve detailed information about a specific movie by its ID.

    This function fetches detailed information about a movie identified by its unique ID.
    If the movie does not exist, a 404 error is returned.
    """
    movie = (
        db.query(Movie)
        .options(
            joinedload(Movie.genres),
            joinedload(Movie.directors),
            joinedload(Movie.stars),
            joinedload(Movie.certification),
        )
        .filter(Movie.id == movie_id)
        .first()
    )

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)


@router.post("/{movie_id}/like")
def like_movie(
    movie_id: int,
    user_id: User = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    existing_like = db.query(Like).filter(Like.movie_id == movie_id, Like.user_id == user_id).first()
    if existing_like:
        raise HTTPException(status_code=400, detail="Movie already liked by this user")

    new_like = Like(movie_id=movie_id, user_id=user_id)
    db.add(new_like)
    db.commit()
    db.refresh(new_like)

    return {"message": "Movie liked", "like_id": new_like.id}


@router.post("/{movie_id}/dislike")
def dislike_movie(
    movie_id: int,
    user_id: User = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    existing_dislike = db.query(Dislike).filter(
        Dislike.movie_id == movie_id, Dislike.user_id == user_id
    ).first()
    if existing_dislike:
        raise HTTPException(status_code=400, detail="Movie already disliked")

    new_dislike = Dislike(movie_id=movie_id, user_id=user_id)
    db.add(new_dislike)
    db.commit()
    db.refresh(new_dislike)

    return {"message": "Movie disliked", "dislike_id": new_dislike.id}


@router.post("/{movie_id}/comments")
def create_comment(
        movie_id: int,
        comment_text: str,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    new_comment = Comment(user_id=user_id, movie_id=movie_id, comment=comment_text)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {"message": f"Comment created with movie id: {movie_id}", "comment_id": new_comment.id}


@router.get("/{movie_id}/comments/")
def get_comments(
        movie_id: int,
        db: Session = Depends(get_db)
):
    comments = db.query(Comment).filter_by(movie_id=movie_id).all()

    if not comments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comments found."
        )

    return comments


@router.post("/comments/{comment_id}/answer")
def reply_to_comment(
    comment_id: int,
    answer_text: str,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    answer = AnswerComment(user_id=user_id, comment_id=comment_id, text=answer_text)
    db.add(answer)
    db.commit()
    db.refresh(answer)

    comment = db.query(Comment).filter_by(id=answer.comment_id).first()
    user_email = db.query(User).filter_by(id=comment.user_id).first().email
    subject = "You have got answer on your comment"
    body = answer_text

    background_tasks.add_task(
        EmailSender.send_email,
        user_email,
        subject,
        body
    )

    return {"message": "Reply created", "reply_id": answer.id}


@router.post("/favorite/")
def add_favorite(
        movie_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db),
):
    existing_movie = db.query(Movie).get(movie_id)

    if not existing_movie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie with the given ID was not found."
        )

    existing_favorite = db.query(Favorite).filter_by(user_id=user_id, movie_id=movie_id).first()
    if existing_favorite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already in favorites"
        )

    favorite = Favorite(user_id=user_id, movie_id=movie_id)
    db.add(favorite)
    db.commit()
    return {"detail": "Movie added to favorites"}


@router.delete("/favorite/")
def remove_favorite(
        movie_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db),
):
    existing_movie = db.query(Movie).get(movie_id)

    if not existing_movie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie with the given ID was not found."
        )

    favorite = db.query(Favorite).filter_by(user_id=user_id, movie_id=movie_id).first()
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie not in favorites"
        )

    db.delete(favorite)
    db.commit()
    return {"detail": f"Movie with id: {movie_id} removed from favorites"}


@router.get(
    "/favorites/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of favorite movies",
    description=(
            "<h3>This endpoint retrieves a paginated list of favorite movies from the database. "
            "Clients can specify the `page` number and the number of items per page using `per_page`. "
            "The response includes details about the movies, total pages, and total items, "
            "along with links to the previous and next pages if applicable.</h3>"
    ),
    responses={
        404: {
            "description": "No favorite movies found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No favorite movies found."}
                }
            },
        }
    }
)
def get_favorite_movies(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
    year: int | None = Query(None, description="Filter by year"),
    min_imdb: float | None = Query(None, description="Filter by min_imdb"),
    max_imdb: float | None = Query(None, description="Filter by max_imdb"),
    genre: str | None = Query(None, description="Filter by genre name"),
    director: str | None = Query(None, description="Filter by director name"),
    star: str | None = Query(None, description="Filter by star name"),
    search: str | None = Query(None, description="Search by title, description, actor or director"),
    sort_by: str | None = Query(None, description="Sort by 'price', 'year', 'votes'"),
    db: Session = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Fetch a paginated list of favorite movies from the database.

    This function retrieves a paginated list of favorite movies, allowing the client to specify
    the page number and the number of items per page. It calculates the total pages
    and provides links to the previous and next pages when applicable.
    """
    offset = (page - 1) * per_page

    query = db.query(Movie).join(Favorite)

    if year:
        query = query.filter(Movie.year == year)
    if min_imdb:
        query = query.filter(Movie.imdb >= min_imdb)
    if max_imdb:
        query = query.filter(Movie.imdb <= max_imdb)
    if director:
        query = query.join(Movie.directors).filter(Director.name.ilike(f"%{director}%"))
    if star:
        query = query.join(Movie.stars).filter(Star.name.ilike(f"%{star}%"))
    if genre:
        query = query.join(Movie.genres).filter(Genre.name.ilike(f"%{genre}%"))

    if search:
        query = (
            query.outerjoin(Movie.directors)
            .outerjoin(Movie.stars)
            .filter(
                or_(
                    Movie.name.ilike(f"%{search}%"),
                    Movie.description.ilike(f"%{search}%"),
                    Director.name.ilike(f"%{search}%"),
                    Star.name.ilike(f"%{search}%"),
                )
            )
        )

    sort_fields = {
        "price": Movie.price,
        "year": Movie.year,
        "votes": Movie.votes,
    }
    if sort_by in sort_fields:
        query = query.order_by(sort_fields[sort_by].desc())

    total_items = query.count()

    movies = query.offset(offset).limit(per_page).all()

    if not movies:
        raise HTTPException(status_code=404, detail="No favorite movies found.")

    movie_list = [
        MovieListItemSchema.model_validate(movie)
        for movie in movies
    ]

    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/movies/favorites/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/favorites/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/genres/",
    summary="Get list of genres",
    description="<h3>This endpoint retrieves a list of genres with the count of movies in each.</h3>",
    responses={
        404: {
            "description": "No genres found.",
            "content": {"application/json": {"example": {"detail": "No genres found."}}},
        }
    },
)
def get_genres(db: Session = Depends(get_db)):
    genres_with_movie_count = (
        db.query(Genre, func.count(Movie.id).label("movie_count"))
        .join(Movie.genres)
        .group_by(Genre.id)
        .all()
    )

    result = [{"name": genre.name, "movie_count": movie_count} for genre, movie_count in genres_with_movie_count]

    return result


@router.get(
    "/genres/{genre_id}/",
    summary="Get genre details by genre name.",
    description="<h3>This endpoint retrieves a genre with all related movies.</h3>",
    responses={
        404: {
            "description": "No genres found.",
            "content": {"application/json": {"example": {"detail": "No genres found."}}},
        }
    },
)
def get_movies_by_genre(
        genre_name: str,
        db: Session = Depends(get_db),
):
    genre = db.query(Genre).filter(Genre.name.ilike(genre_name)).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")
    return genre.movies


@router.put(
    "/{movie_id}/rate",
    summary="Rate a movie by its ID",
    description="<h3>Rate movies on a 10-point scale.</h3>",
    responses={
        400: {
            "description": "Bad Request - The provided refresh token is invalid or expired.",
            "content": {"application/json": {"example": {"detail": "Token has expired."}}},
        },
        401: {
            "description": "Unauthorized - Refresh token not found.",
            "content": {"application/json": {"example": {"detail": "Refresh token not found."}}},
        },
        404: {
            "description": "Not Found - The movie does not exist.",
            "content": {"application/json": {"example": {"detail": "Movie not found."}}},
        },
    },
)
def rate_movie(
        movie_id: int,
        rating: int = Query(ge=0, le=10),
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id),
):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    movie.votes += 1

    total_rating = (movie.rating * (movie.votes - 1)) + rating
    movie.rating = round(total_rating / movie.votes, 1)

    db.commit()

    return {"movie_id": movie.id, "new_rating": movie.rating, "total_votes": movie.votes}

    # user_rating = db.query(Rating).filter_by(user_id=user_id, movie_id=movie_id).first()
    #
    # if user_rating:
    #     previous_rating = user_rating.rating
    #     user_rating.rating = rating
    # else:
    #     previous_rating = None
    #     user_rating = Rating(user_id=user_id, movie_id=movie_id, rating=rating)
    #     db.add(user_rating)
    #     movie.votes += 1
    #
    # if previous_rating is not None:
    #     total_rating = (movie.rating * movie.votes) - previous_rating + rating
    # else:
    #     total_rating = (movie.rating * (movie.votes - 1)) + rating
    #
    # movie.rating = round(total_rating / movie.votes, 1)
    #
    # db.commit()
    #
    # return MovieDetailSchema.model_validate(movie)


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    description=(
            "<h3>This endpoint allows clients to add a new movie to the database. "
            "It accepts details such as name, date, genres, actors, languages, and "
            "other attributes. The associated country, genres, actors, and languages "
            "will be created or linked automatically.</h3>"
    ),
    responses={
        201: {
            "description": "Movie created successfully.",
        },
        400: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        }
    },
    status_code=201
)
def create_movie(
        movie_data: MovieCreateSchema,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
) -> MovieDetailSchema:
    """
    Add a new movie to the database.

    This endpoint allows the creation of a new movie with details such as
    name, release date, genres, actors, and languages. It automatically
    handles linking or creating related entities.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.group.name not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403, detail="You do not have access to perform this action."
        )
    existing_movie = db.query(Movie).filter(
        Movie.name == movie_data.name,
        Movie.year == movie_data.year
    ).first()

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release year '{movie_data.year}' already exists."
        )

    try:
        existing_certification = db.query(Certification).filter_by(name=movie_data.certification).first()
        if not existing_certification:
            new_certification = Certification(name=movie_data.certification)
            db.add(new_certification)
            db.flush()
            certification = new_certification
        else:
            certification = existing_certification

        genres = []
        for genre_name in movie_data.genres:
            genre = db.query(Genre).filter_by(name=genre_name).first()
            if not genre:
                genre = Genre(name=genre_name)
                db.add(genre)
                db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star = db.query(Star).filter_by(name=star_name).first()
            if not star:
                star = Star(name=star_name)
                db.add(star)
                db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director = db.query(Director).filter_by(name=director_name).first()
            if not director:
                director = Director(name=director_name)
                db.add(director)
                db.flush()
            directors.append(director)

        movie = Movie(
            uuid=movie_data.uuid,
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            genres=genres,
            stars=stars,
            directors=directors,
            certification=certification,
        )
        db.add(movie)
        db.commit()
        db.refresh(movie)

        return MovieDetailSchema.model_validate(movie)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.delete(
    "/{movie_id}/",
    summary="Delete a movie by ID",
    description=(
        "<h3>Delete a specific movie from the database by its unique ID.</h3>"
        "<p>If the movie exists, it will be deleted. If it does not exist, "
        "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
def delete_movie(
    movie_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Delete a specific movie by its ID.

    This function deletes a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.group.name not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403, detail="You do not have access to perform this action."
        )
    movie = db.query(Movie).filter(Movie.id == movie_id).first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    db.delete(movie)
    db.commit()
    return {"detail": "Movie deleted successfully."}


@router.patch(
    "/movies/{movie_id}/",
    summary="Update a movie by ID",
    description=(
        "<h3>Update details of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates the details of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    }
)
def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update a specific movie by its ID.

    This function updates a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.group.name not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=403, detail="You do not have access to perform this action."
        )
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        db.commit()
        db.refresh(movie)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")
    else:
        return {"detail": "Movie updated successfully."}
