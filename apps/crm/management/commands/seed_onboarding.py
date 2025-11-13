from django.core.management.base import BaseCommand
from apps.crm.models import Pipeline, Stage

class Command(BaseCommand):
    help = "Создаёт/обновляет воронку 'Подключение объекта'"

    def handle(self, *args, **kwargs):
        pipeline, _ = Pipeline.objects.get_or_create(code="onboarding", defaults={"name":"Подключение объекта"})
        stages = [
            ("Новый лид","new",1,False,False),
            ("Первичный контакт","contacted",2,False,False),
            ("Оценка объекта / выезд","inspection",3,False,False),
            ("Подготовка предложения","proposal",4,False,False),
            ("Отправлено предложение","offer_sent",5,False,False),
            ("Согласование договора","contract_negotiation",6,False,False),
            ("Договор подписан / объект принят","contract_signed",7,True,False),
            ("Отказ / неактуально","lost",8,False,True),
        ]
        for name,code,order,won,lost in stages:
            Stage.objects.update_or_create(
                pipeline=pipeline, code=code,
                defaults={"name":name,"order":order,"is_won":won,"is_lost":lost}
            )
        self.stdout.write(self.style.SUCCESS("Воронка готова"))
