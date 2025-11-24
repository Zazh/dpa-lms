from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def backoffice_required(view_func):
    """
    Декоратор для проверки доступа к backoffice
    Доступ имеют: инструкторы, менеджеры (не студенты)
    """

    @wraps(view_func)
    @login_required(login_url='/admin/login/')  # Используем стандартный логин Django
    def wrapper(request, *args, **kwargs):
        if not request.user.is_backoffice_user():
            messages.error(request, 'Доступ запрещен. Только для сотрудников.')
            return redirect('backoffice:no_access')

        return view_func(request, *args, **kwargs)

    return wrapper


def instructor_required(view_func):
    """
    Декоратор для инструкторов (любого уровня)
    """

    @wraps(view_func)
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_instructor():
            messages.error(request, 'Доступ запрещен. Только для инструкторов.')
            return redirect('backoffice:no_access')

        return view_func(request, *args, **kwargs)

    return wrapper


def super_instructor_required(view_func):
    """
    Декоратор для супер-инструктора
    """

    @wraps(view_func)
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_super_instructor():
            messages.error(request, 'Доступ запрещен. Только для супер-инструкторов.')
            return redirect('backoffice:no_access')

        return view_func(request, *args, **kwargs)

    return wrapper


def manager_required(view_func):
    """
    Декоратор для менеджеров (любого уровня)
    """

    @wraps(view_func)
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_manager():
            messages.error(request, 'Доступ запрещен. Только для менеджеров.')
            return redirect('backoffice:no_access')

        return view_func(request, *args, **kwargs)

    return wrapper


def super_manager_required(view_func):
    """
    Декоратор для супер-менеджера
    """

    @wraps(view_func)
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_super_manager():
            messages.error(request, 'Доступ запрещен. Только для супер-менеджеров.')
            return redirect('backoffice:no_access')

        return view_func(request, *args, **kwargs)

    return wrapper