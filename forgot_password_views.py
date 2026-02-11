# Forgot Password Views - Add to views.py

# Store OTPs temporarily (in production, use cache or database)
_otp_storage = {}

@require_POST
def send_otp(request):
    """Send OTP to user's email for password reset"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        
        if not email:
            return JsonResponse({'status': 'error', 'message': 'Email is required'}, status=400)
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'No account found with this email'}, status=404)
        
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Store OTP with timestamp (expires in 10 minutes)
        _otp_storage[email] = {
            'otp': otp,
            'timestamp': timezone.now()
        }
        
        # Send email
        try:
            subject = 'FilmOracle - Password Reset OTP'
            message = f"""Hello {user.username},

You requested a password reset for your FilmOracle account.

Your OTP code is: {otp}

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
FilmOracle Team"""
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return JsonResponse({'status': 'success', 'message': 'OTP sent to your email'})
        except Exception as e:
            print(f"Error sending email: {e}")
            return JsonResponse({'status': 'error', 'message': 'Failed to send email. Please try again.'}, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    except Exception as e:
        print(f"Error in send_otp: {e}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)


@require_POST
def reset_password_with_otp(request):
    """Reset password using OTP verification"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        otp = data.get('otp', '').strip()
        new_password = data.get('new_password', '')
        
        if not all([email, otp, new_password]):
            return JsonResponse({'status': 'error', 'message': 'All fields are required'}, status=400)
        
        # Check if OTP exists and is valid
        if email not in _otp_storage:
            return JsonResponse({'status': 'error', 'message': 'OTP not found or expired'}, status=400)
        
        stored_otp_data = _otp_storage[email]
        stored_otp = stored_otp_data['otp']
        timestamp = stored_otp_data['timestamp']
        
        # Check if OTP has expired (10 minutes)
        if (timezone.now() - timestamp).total_seconds() > 600:
            del _otp_storage[email]
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please request a new one.'}, status=400)
        
        # Verify OTP
        if otp != stored_otp:
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP'}, status=400)
        
        # Get user and reset password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Remove OTP from storage
            del _otp_storage[email]
            
            return JsonResponse({'status': 'success', 'message': 'Password reset successfully'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    except Exception as e:
        print(f"Error in reset_password_with_otp: {e}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
