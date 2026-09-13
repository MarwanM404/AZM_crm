# Working a ticket — one page

*Referenced by SC-008: an agent should complete the full flow on first attempt with no more
guidance than this page.*

## English

**Signing in.** Go to `/sign-in/` with the email address your administrator set up. If you
have never set a password, ask them to set one — a new account cannot sign in until it has.

**Your queue** (`/tickets/`) shows every ticket in your department, not only yours. That is
deliberate: you can see what colleagues are working on, spot duplicates, and pick up work when
someone is away. Sort order is most urgent first, then longest waiting.

**Taking a ticket.** Unassigned tickets show a **Take** button. If two of you click it at the
same moment, exactly one wins — the other sees "already assigned to another agent". That is
the system working, not an error.

**Replying.** Open a ticket and use **Reply to customer**. It is delivered by email in the
customer's own language and appears on the thread. If delivery fails you will see "Not
delivered" on the message, with the reason — the reply is not lost, and you can try again.

**Internal notes.** The second tab, **Internal note**, is for your colleagues. It is never
emailed and never shown to the customer. On the thread it is marked with a lock and the words
"Internal note — not visible to the customer" on an amber panel. If you cannot see that
banner, you are writing a public reply.

**Changing a ticket.** Category and priority are on the right and save as you change them.
Status moves along fixed steps — a ticket is resolved before it is closed, and a customer's
reply reopens a resolved ticket automatically, so nothing gets lost after you close it.

**Customers.** `/customers/` lists organizations; each one shows every ticket from every
person who works there, plus your team's notes. `/customers/unlinked/` holds people who wrote
in before we knew where they work — link them to an organization when you recognize them.
Their existing tickets follow them; tickets they raised under a previous employer stay where
they were.

**Language.** Switch between English and العربية at the bottom of the sidebar. The choice
follows your account, so it holds on any computer you sign in from.

---

### Live chat

**Going online.** Chat is at `/chat/console/`. Nothing reaches you until you press **Go
online** — the system never assigns a conversation to someone who has not said they are there.
Customers are only offered chat while at least one agent is online; when nobody is, they see
the request form instead. So going online is not a preference. It is what opens the desk.

**Capacity.** You hold three conversations at once by default, and a fourth goes to somebody
else or waits in the queue. The number beside your status is how many you can still take. An
administrator can change it for you.

**Going offline.** You cannot go offline while you are still holding conversations. The button
refuses and tells you how many are open. End them first, or hand them over by ending and
letting the queue reassign. This exists because "I am done for the day" would otherwise leave
a customer typing into a conversation nobody is reading.

**If your connection drops.** Come back within a minute and you keep your conversations, with
everything said while you were away. Longer than that and they return to the queue with their
full history, and the customer is told they are being reconnected — they are not asked to
start again.

**The ticket.** Every chat is a ticket from the moment it starts, so nothing is ever lost if a
conversation ends badly. The customer is not shown the reference until it ends, because you
may attach the conversation to a ticket they already had. If you do, the whole transcript
moves there and the placeholder is retired. You can only attach to the same customer's open
tickets.

**Ending.** Ending a chat and solving the problem are separate. Tick **resolved** only if it
is; otherwise the ticket stays open for you or a colleague to finish.

**Private notes.** A note from a supervisor appears in your conversation marked with a lock and
the words *the customer cannot see this*. It is never sent to the customer — there is no route
from that note to their window, not a setting that might be wrong. You cannot reply to it in
the conversation; speak to your supervisor as you normally would.

### Being observed

A supervisor in your department can open one of your live conversations and read it as it
happens, along with the customer's history. **You are told when they do**, by name, in the
conversation itself — and told again when they stop.

Every observation is recorded: who watched which conversation, and when. That record cannot be
edited or deleted by anyone, including the supervisor who made it and the administrator who
can read the audit log.

Observation is reading and coaching only. A supervisor watching your conversation cannot write
to the customer, cannot end the conversation, and cannot take it from you. What they can do is
send you a private note. Nothing they do appears to the customer, who is not told that anyone
else is present.

### If a screen says your account has no department

Every screen in this product shows you your own department and branch and nothing else. An
account without them matches nothing, so the queue, the customer list and the staff accounts
list all come up empty — and the emptiness is real, not a fault.

If that is you, the screens now say so rather than just appearing empty. An administrator can
set their own department and branch from that notice, once: it exists because the first
account on a new installation has no scope and there is nobody else to ask. Anyone else should
ask an administrator.

This is the only place in the product where somebody sets their own scope, and it closes as
soon as it is used. Changing it afterwards is an administrator's job, as it is for everyone.

### Setting up a new installation

Create the first administrator with `bootstrap_admin`, not `createsuperuser`. The second asks
only for an email address and a name — it cannot sensibly ask for a department, because on an
empty database there is none to choose — and the account it makes can see nothing. `README.md`
has the exact command.

## بالعربية

**تسجيل الدخول.** ادخل إلى `/sign-in/` باستخدام البريد الإلكتروني الذي أنشأه لك المسؤول. إذا
لم تُعيَّن لك كلمة مرور بعد، اطلب من المسؤول تعيينها — لا يمكن للحساب الجديد تسجيل الدخول
قبل ذلك.

**قائمة التذاكر** (`/tickets/`) تعرض كل تذاكر قسمك، وليس تذاكرك وحدها. هذا مقصود: لترى ما
يعمل عليه زملاؤك، وتكتشف التذاكر المكررة، وتستلم العمل عند غياب أحدهم. الترتيب: الأعجل أولًا،
ثم الأطول انتظارًا.

**استلام تذكرة.** التذاكر غير المُسنَدة تعرض زر **استلام**. إذا ضغط زميلان الزر في اللحظة
نفسها، ينجح واحد فقط، ويظهر للآخر أن التذكرة مُسنَدة بالفعل. هذا عمل النظام الصحيح وليس خطأً.

**الرد.** افتح التذكرة واستخدم **الرد على العميل**. يُرسل الرد بالبريد الإلكتروني بلغة العميل
ويظهر في سجل المحادثة. إذا فشل الإرسال ستظهر عبارة "لم يتم التسليم" مع السبب — الرد لا يضيع،
ويمكنك المحاولة مجددًا.

**الملاحظات الداخلية.** التبويب الثاني، **ملاحظة داخلية**، مخصص لزملائك. لا تُرسل بالبريد ولا
تظهر للعميل أبدًا. تظهر في سجل المحادثة بعلامة قفل وبعبارة "ملاحظة داخلية — غير ظاهرة للعميل"
على خلفية كهرمانية. إن لم ترَ هذه العبارة، فأنت تكتب ردًا عامًا يراه العميل.

**تعديل التذكرة.** التصنيف والأولوية على الجانب، ويُحفظان فور تغييرهما. تنتقل الحالة عبر خطوات
محددة — تُحل التذكرة قبل إغلاقها، ورد العميل يعيد فتح التذكرة المحلولة تلقائيًا، فلا يضيع شيء
بعد الإغلاق.

**العملاء.** `/customers/` يعرض المنشآت، وتعرض كل منشأة تذاكر جميع العاملين فيها مع ملاحظات
الفريق. `/customers/unlinked/` يضم من راسلونا قبل أن نعرف جهة عملهم — اربطهم بمنشأة عند
التعرّف عليهم. تنتقل تذاكرهم الحالية معهم، أما التذاكر التي فُتحت تحت جهة عمل سابقة فتبقى
كما هي.

**اللغة.** بدّل بين العربية و English من أسفل القائمة الجانبية. يُحفظ الاختيار في حسابك،
فيبقى على أي جهاز تسجّل الدخول منه.

### المحادثة المباشرة

**الاتصال.** المحادثات في `/chat/console/`. لا يصلك شيء حتى تضغط **اتصال** — لا يُسنِد النظام
محادثة إلى شخص لم يعلن حضوره. ولا تُعرض المحادثة على العملاء إلا إذا كان هناك موظف واحد على
الأقل متصلًا؛ وإن لم يكن، يظهر لهم نموذج الطلب بدلًا منها. فالاتصال ليس تفضيلًا شخصيًا، بل هو
ما يفتح المكتب.

**السعة.** تتولى ثلاث محادثات في وقت واحد افتراضيًا، والرابعة تذهب لزميل أو تنتظر في الطابور.
الرقم بجانب حالتك هو عدد ما يمكنك استقباله بعد. ويمكن للمسؤول تغييره لك.

**قطع الاتصال.** لا يمكنك قطع الاتصال وأنت ما زلت تتولى محادثات. سيرفض الزر ويخبرك بعددها
المفتوح. أنهِ المحادثات أولًا، أو سلّمها بإنهائها ليعيد الطابور إسنادها. هذا موجود لأن "انتهى
دوامي" كان سيترك عميلًا يكتب في محادثة لا يقرأها أحد.

**إذا انقطع اتصالك.** إن عدت خلال دقيقة احتفظت بمحادثاتك، وبكل ما قيل أثناء غيابك. وإن طالت
المدة عادت المحادثات إلى الطابور بسجلها كاملًا، ويُبلَّغ العميل بأنه يُعاد توصيله — ولا
يُطلب منه أن يبدأ من جديد.

**التذكرة.** كل محادثة هي تذكرة منذ لحظة بدئها، فلا يضيع شيء إذا انتهت المحادثة على نحو
غير متوقع. ولا يُعرض الرقم المرجعي على العميل حتى تنتهي، لأنك قد تُرفق المحادثة بتذكرة
لديه أصلًا. وإن فعلت، ينتقل نص المحادثة كاملًا إليها وتُسحب التذكرة المؤقتة. ولا يمكنك
الإرفاق إلا بتذاكر العميل نفسه المفتوحة.

**الإنهاء.** إنهاء المحادثة وحلّ المشكلة أمران منفصلان. علّم **تم الحل** فقط إن كان كذلك؛
وإلا تبقى التذكرة مفتوحة لك أو لزميل يكملها.

**الملاحظات الخاصة.** تظهر ملاحظة المشرف في محادثتك بعلامة قفل وعبارة *لا يراها العميل*. ولا
تُرسل إلى العميل أبدًا — لا يوجد طريق أصلًا من تلك الملاحظة إلى نافذته، وليست مجرد إعداد قد
يكون خاطئًا. ولا يمكنك الرد عليها داخل المحادثة؛ تحدّث إلى مشرفك كالمعتاد.

### حين تكون تحت المراقبة

يستطيع المشرف في قسمك فتح إحدى محادثاتك الجارية وقراءتها لحظة بلحظة، مع سجل العميل. **وتُبلَّغ
حين يفعل**، بالاسم، داخل المحادثة نفسها — وتُبلَّغ مرة أخرى حين يتوقف.

كل مراقبة تُسجَّل: من راقب أي محادثة، ومتى. ولا يمكن لأحد تعديل ذلك السجل أو حذفه، بما في ذلك
المشرف الذي أنشأه والمسؤول الذي يستطيع قراءة سجل التدقيق.

المراقبة قراءة وتوجيه فقط. المشرف الذي يراقب محادثتك لا يستطيع الكتابة إلى العميل، ولا إنهاء
المحادثة، ولا أخذها منك. ما يستطيعه هو إرسال ملاحظة خاصة إليك. ولا يظهر شيء مما يفعله للعميل،
الذي لا يُبلَّغ بوجود أي شخص آخر.

### إذا ظهرت لك رسالة بأن حسابك بلا قسم

كل شاشة في هذا النظام تعرض لك قسمك وفرعك وحدهما. والحساب الذي لا قسم له ولا فرع لا يطابق
شيئًا، فتظهر قائمة التذاكر وقائمة العملاء وحسابات الموظفين فارغة — وهذا فراغ حقيقي، وليس عطلًا.

إن كان هذا حالك، فالشاشات تخبرك بذلك الآن بدل أن تبدو فارغة بلا سبب. ويستطيع المسؤول تعيين
قسمه وفرعه من تلك الرسالة، مرة واحدة: فهذا موجود لأن أول حساب في نظام جديد بلا نطاق ولا يوجد
من يُسأل. أما غير المسؤول فعليه أن يطلب ذلك من المسؤول.

هذا هو الموضع الوحيد في النظام الذي يعيّن فيه أحدٌ نطاق نفسه، ويُغلق بمجرد استخدامه. أما
تغييره بعد ذلك فهو من عمل المسؤول، كحال الجميع.

### تهيئة نظام جديد

أنشئ أول مسؤول بالأمر `bootstrap_admin` لا بـ `createsuperuser`. فالثاني لا يسأل إلا عن بريد
إلكتروني واسم — ولا يمكنه أن يسأل عن القسم، إذ لا قسم في قاعدة بيانات فارغة — والحساب الذي
ينشئه لا يرى شيئًا. الأمر كاملًا في `README.md`.
