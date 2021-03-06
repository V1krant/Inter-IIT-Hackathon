from django.shortcuts import render, redirect, get_object_or_404
from dashboard.models import Post
from dashboard.serializers import PostSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import views, permissions, generics, mixins, status
from django.http import Http404
from django.core.mail import send_mail
from django.conf import settings
from authentication.models import Department
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from .permissions import IsOfficial
from .decorators import officials_only
from django.contrib.auth.decorators import login_required


def welcome(request):
    return render(request, 'admindb/welcome.html')

@login_required
@officials_only
def progressdashboard(request):
    complaints = Post.objects.filter(official=request.user, progress_report=True, ignored=False, is_resolved=False, spam=False)
    return render(request, 'admindb/dashboard.html', {'complaints': complaints})

@login_required
@officials_only
def complaintdashboard(request):
    complaints = Post.objects.filter(official=request.user, progress_report=False, ignored=False, is_resolved=False, spam=False)
    return render(request, 'admindb/dashboard.html', {'complaints': complaints})

@login_required
@officials_only
def forward(request, pk):
    complaint = get_object_or_404(Post, pk = pk)
    # declinenotif = "Your complaint with ID "+ str(complaint.complaint_id)[:8] + " is declined"
    # Notification.objects.create(user=complaint.filer, notification = declinenotif
    # messages.success(request, f'Complaint archived and email sent to user successfully!')

    return render(request, 'admindb/forward.html', {'complaint': complaint})

@login_required
@officials_only
def decline(request, pk):
    complaint = get_object_or_404(Post, id = pk)
    complaint.ignored = True
    complaint.save()
    messages.success(request, f'Complaint declined successfully!')
    return redirect('admindb/dashboard')

##############################################

@login_required
@officials_only
def mark_spam(request, pk):
    complaint = get_object_or_404(Complaint, pk = pk)
    
    spamnotif = "Your complaint with ID "+ str(complaint.complaint_id)[:8] + " is marked as spam, this is a warning that you should file truthful complaints"
    Notification.objects.create(user=complaint.filer, notification = spamnotif)
    
    complaint.filer.profile.spamcount += 1
    
    if complaint.filer.profile.spamcount > 4 and complaint.filer.profile.spamcount % 5 == 0:
        complaint.filer.profile.rewards -= 10 
        deductionnotif = "Your complaint with ID "+ str(complaint.complaint_id)[:8] + " is marked as spam, and due to continuous spamming, a reward of 10 is deducted from your account"
        Notification.objects.create(user=complaint.filer, notification = deductionnotif)

    complaint.filer.profile.save()
    complaint.delete()
    messages.success(request, f'Complaint marked as spam successfully!')
    return redirect('dashboard')

@login_required
@officials_only
def approve_success(request, pk):
    complaint = get_object_or_404(Complaint, pk = pk)
    complaint.is_verified = True
    complaint.status = 'Verified'
    points = 10
    complaint.filer.profile.rewards += points
    complaint.filer.profile.save()
    complaint.save()
    approvenotif = "Your complaint with ID "+ str(complaint.complaint_id)[:8] + " is approved and reward of 10 is credited to your account. Thanks for bringing this to our notice."
    Notification.objects.create(user=complaint.filer, notification = approvenotif)
    messages.success(request, f'Complaint verified successfully!')
    return render(request, 'admindb/approved_complaint.html', {'complaint': complaint, 'reward': points})

@login_required
@officials_only
def mark_solved(request, pk):
    complaint = get_object_or_404(Complaint, pk = pk)
    complaint.is_settled = True
    complaint.status = 'Solved'
    complaint.save()
    successnotif = "Your complaint with ID "+ str(complaint.complaint_id)[:8] + " is settled, Keep helping us ahead."
    Notification.objects.create(user=complaint.filer, notification = successnotif)
    messages.success(request, f'Complaint marked solved successfully!')
    return render(request, 'admindb/solved_complaint.html', {'complaint': complaint})

@login_required
@officials_only
def verified_complaints(request):
    complaints = Complaint.objects.filter(is_verified = True, is_settled = False).order_by('-date_filed')
    return render(request, 'admindb/verified_complaints.html', {'complaints': complaints})

@login_required
@officials_only
def solved_complaints(request):
    complaints = Complaint.objects.filter(is_settled= True).order_by('-date_filed')
    return render(request, 'admindb/solved_complaints.html', {'complaints': complaints})

##########################################################################################################

@api_view(['GET', 'POST'])
@permission_classes([IsOfficial, IsAuthenticated])
def create_location(request):
    if request.method == 'GET':
        questions = curr_assign.questions.all()
        serializer = LocationSerializer(questions, many=True)
        return Response(serializer.data)
    
    if request.method == 'POST':
        post_data = []
        for location in request.data:
            serializer = LocationSerializer(data=question)
            if serializer.is_valid():
                serializer.save()
                post_data.append(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(post_data, status=status.HTTP_201_CREATED)

class AdminListComplaint(generics.GenericAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsOfficial]
    def get(self, request, format = None):
        # if not self.request.user.is_staff:
        #     return Response({'message': 'You do not have rights to access this page'}, status=status.HTTP_403_FORBIDDEN)
        
        posts = Post.objects.filter(official=self.request.user, progress_report=False)
        posts_list = PostSerializer(posts, many=True)  
        return Response(posts_list.data)

class AdminListProgress(generics.GenericAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsOfficial]
    def get(self, request, format = None):
        posts = Post.objects.filter(official=self.request.user, progress_report=True)
        posts_list = PostSerializer(posts, many=True)  
        return Response(posts_list.data)

# action by which admin will delete the post or ignore them
class IgnorePost(views.APIView):
    permission_classes = [IsAuthenticated, IsOfficial]

    def post(self, request, pk, format=None):
        try:
            post = Post.objects.get(id=pk)
        except Post.DoesNotExist:
            raise Http404
        
        post.ignored = True
        email = post.author.email
        token = post.token
        date = post.date_posted
        reason = request.data.get('reason')
        send_mail(
            'Report closed by admin action',
            'Your post with Ref. No. {0} posted on {1}, has been closed by Admin action. With the following reason: {2}'.format(token, date, reason),
            'admin@srlms.com',
            [email],
            fail_silently=False,
        )
        post.save()
        return Response({'message': 'success'}, status=status.HTTP_200_OK)

# resolve post view
class ResolvePost(views.APIView):
    permission_classes = [IsAuthenticated, IsOfficial]

    def post(self, request, pk, format=None):
        try:
            post = Post.objects.get(id=pk)
        except Post.DoesNotExist:
            raise Http404
        
        post.is_resolved = True
        email = post.author.email
        token = post.token
        date = post.date_posted
        author = post.author
        if post.was_travelled:
            author.points += 10
        author.points += 10
        author.save()
        send_mail(
            'Report resolved by admin action',
            'Your post with Ref. No. {0} posted on {1}, has been resolved by Admin action. Thanks for supporting the government with this initiative. You have been credited 10 points which you can redeem on SRLMS API supported authorities like toll taxes.'.format(token, date),
            'admin@srlms.com',
            [email],
            fail_silently=False,
        )
        post.save()
        return Response({'message': 'success'}, status=status.HTTP_200_OK)



@api_view(['GET'])
def deplist(request):
    departments = list(Department.objects.all().values())
    return JsonResponse(departments, safe=False)

class ForwardPost(views.APIView):
    permission_classes = [IsAuthenticated, IsOfficial]

    def post(self, request, pk, format=None):
        try:
            post = Post.objects.get(id=pk)
        except Post.DoesNotExist:
            raise Http404

        department = request.data.get('department')
        department = Department.objects.get(name=department)
        officials = department.user_set.all()
        post.officials.remove(self.request.user)
        for official in officials:
            post.officials.add(official)
        post.save()
        return Response({'message': 'success'}, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOfficial])
def mark_spam(request):
    post_id = request.data.get("id")
    post = Post.objects.get(id = post_id)
    author = post.author
    email = author.email
    token = post.token
    post.spam = True
    author.spamcount += 1
    post.save()


    if author.spamcount >= settings.SPAM_THRESHOLD: #Limit is the limit set by admin authorities
        author.freeze = True
        author.contributions = 0
        author.freeze_date = datetime.datetime.now().date() + datetime.timedelta(days=settings.SPAM_TOLERANCE_DAYS)     #unfreeze after 10 days
    
    author.save()
    send_mail(
        'Report spammed by admin action',
        'Your post with Ref. No. {0} posted on {1}, has been marked spammed by Admin action.'.format(token, date),
        'admin@srlms.com',
        [email],
        fail_silently=False,
    )
    return JsonResponse(request.data)

