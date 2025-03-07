from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from src.database.models.movies import (
    Movie, Genre, Star, Director, Certification
)
from src.database import Base
from src.main import app

# Setting up the test database (SQLite in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///./src/tests/test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """ Creates a fresh database session for each test. """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def genre(db_session):
    genre = Genre(name="Action")
    db_session.add(genre)
    db_session.commit()
    db_session.refresh(genre)
    return genre


@pytest.fixture(scope="function")
def certification(db_session):
    certification = Certification(name="TV-14")
    db_session.add(certification)
    db_session.commit()
    db_session.refresh(certification)
    return certification


@pytest.fixture(scope="function")
def movie(db_session, genre, certification):
    movie = Movie(
        name="The Terminator",
        year=1984,
        time=107,
        imdb=8.1,
        votes=957000,
        price=10.00,
        certification_id=certification.id,
        description="A cyborg is sent from the future to kill the mother of the future leader of mankind.",
    )
    movie.genres.append(genre)
    db_session.add(movie)
    db_session.commit()
    db_session.refresh(movie)
    return movie


@pytest.fixture(scope="function")
def star(db_session):
    star = Star(name="Linda Hamilton")
    db_session.add(star)
    db_session.commit()
    db_session.refresh(star)
    return star


@pytest.fixture(scope="function")
def director(db_session):
    director = Director(name="James Cameron")
    db_session.add(director)
    db_session.commit()
    db_session.refresh(director)
    return director


def test_create_movie(db_session):
    movie = Movie(
        name="The Terminator",
        year=1984,
        time=107,
        imdb=8.1,
        votes=957000,
        price=Decimal("10.00"),
        certification_id=1,
        description="A cyborg is sent from the future to kill the mother of the future leader of mankind."
    )
    db_session.add(movie)
    db_session.commit()

    saved_movie = db_session.query(Movie).filter_by(name="The Terminator").first()
    assert saved_movie.price == Decimal("10.00")


def test_movie_with_multiple_genres(db_session, movie, genre):
    """ Test adding multiple genres to a movie. """
    love = Genre(name="Love")
    db_session.add(love)
    db_session.commit()

    movie.genres.append(love)
    db_session.commit()

    assert love in movie.genres
    assert len(movie.genres) == 2


def test_add_star_to_movie(db_session, movie, star):
    """ Test adding a star to a movie. """
    movie.stars.append(star)
    db_session.commit()

    assert star in movie.stars


def test_add_director_to_movie(db_session, movie, director):
    """ Test adding a director to a movie"""
    movie.directors.append(director)
    db_session.commit()

    assert director in movie.directors
