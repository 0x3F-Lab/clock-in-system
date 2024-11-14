from django.shortcuts import render, redirect
from .models import User

def login_view(request):
    return render(request, 'auth_app/login.html')

def user_list(request):
    users = User.objects.all()
    return render(request, 'auth_app/user_list.html', {'users': users})

def create_user(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        password = request.POST['password']
        
        user = User(name=name, email=email, password=password)
        user.save()
        
        return redirect('user_list')
    return render(request, 'auth_app/create_user.html')