from pydantic import BaseModel, Field


class WorkoutMetadataUpdate(BaseModel):
    session_rpe: int | None = Field(default=None, ge=1, le=10)
    lower_back_pain: int | None = Field(default=None, ge=0, le=10)


class WorkoutUpdateRequest(BaseModel):
    created_at: str | None = Field(default=None, min_length=16, max_length=19)
    session_rpe: int | None = Field(default=None, ge=1, le=10)
    lower_back_pain: int | None = Field(default=None, ge=0, le=10)


class AddExerciseRequest(BaseModel):
    exercise_id: int = Field(ge=1)


class ExerciseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ExerciseUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AddSetRequest(BaseModel):
    weight: float = Field(ge=0)
    reps: int = Field(ge=1, le=100)


class UpdateSetRequest(BaseModel):
    weight: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=1, le=100)
