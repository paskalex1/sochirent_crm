from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import EmailLoginForm


def login_view(request):
    if request.user.is_authenticated:
        redirect_to = request.GET.get("next") or getattr(
            settings, "LOGIN_REDIRECT_URL", "/"
        )
        return redirect(redirect_to)

    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            login(request, user)
            messages.success(request, "Вы успешно вошли в систему.")
            redirect_to = request.GET.get("next") or getattr(
                settings, "LOGIN_REDIRECT_URL", "/"
            )
            return redirect(redirect_to)
    else:
        form = EmailLoginForm()

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    redirect_to = getattr(settings, "LOGOUT_REDIRECT_URL", "/")
    return redirect(redirect_to)

