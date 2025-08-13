from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, authenticate, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from .serializers import UserRegistrationSerializer, UserSerializer, LoginSerializer
from .models import User


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user."""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login user and return token."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user by deleting token."""
    try:
        request.user.auth_token.delete()
        return Response({'message': 'Successfully logged out'})
    except:
        return Response({'error': 'Error logging out'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """Get user profile."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# Web Views
@csrf_protect
def web_login(request):
    """Web login page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            # Create or get token for API calls
            token, created = Token.objects.get_or_create(user=user)
            # Store token in session for JavaScript access
            request.session['auth_token'] = token.key
            return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {
                'error': 'Invalid email or password',
                'email': email
            })
    
    return render(request, 'accounts/login.html')


@csrf_protect
def web_register(request):
    """Web registration page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validation
        if password != password_confirm:
            return render(request, 'accounts/register.html', {
                'error': 'Passwords do not match',
                'email': email,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
        
        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/register.html', {
                'error': 'Email already exists',
                'email': email,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
        
        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/register.html', {
                'error': 'Username already exists',
                'email': email,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            # Create token for API calls
            token, created = Token.objects.get_or_create(user=user)
            request.session['auth_token'] = token.key
            return redirect('dashboard')
        except Exception as e:
            return render(request, 'accounts/register.html', {
                'error': 'Registration failed. Please try again.',
                'email': email,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
    
    return render(request, 'accounts/register.html')


@login_required
def dashboard(request):
    """Dashboard page for authenticated users."""
    return render(request, 'dashboard.html', {
        'user': request.user,
        'auth_token': request.session.get('auth_token')
    })


@login_required
def audio_player(request, file_id):
    """Audio player page for a specific file."""
    from apps.transcription.models import AudioFile, Transcription
    import json
    
    try:
        audio_file = AudioFile.objects.get(id=file_id, owner=request.user)
        transcription = None
        word_timestamps = []
        
        try:
            transcription = audio_file.transcription
            # Get word-level timestamps for accurate highlighting
            if transcription:
                words = transcription.words.all().order_by('word_index')
                word_timestamps = [
                    {
                        'word': word.word,
                        'start': word.start_time,
                        'end': word.end_time,
                        'index': word.word_index
                    }
                    for word in words
                ]
        except Transcription.DoesNotExist:
            pass
        
        return render(request, 'audio_player.html', {
            'audio_file': audio_file,
            'transcription': transcription,
            'word_timestamps_json': json.dumps(word_timestamps),
            'user': request.user
        })
    except AudioFile.DoesNotExist:
        from django.http import Http404
        raise Http404("Audio file not found")


def web_logout(request):
    """Web logout."""
    if request.user.is_authenticated:
        # Delete the auth token
        try:
            request.user.auth_token.delete()
        except:
            pass
    
    logout(request)
    return redirect('web_login')