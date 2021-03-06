angular.module('resources.users',['ngResource'])

  .factory('Users', function ($resource) {

    return $resource(
      "/profile/:id",
      {},
      {
        query:{
          method: "GET",
          params: {embedded: "@embedded"}
        },
        patch:{
          method: "POST",
          headers: {'X-HTTP-METHOD-OVERRIDE': 'PATCH'},
          params:{id:"@about.id"} // use the 'id' property of submitted data obj
        }
      }
    )
  })



  .factory("ProfileWithoutProducts", function($resource){
    return $resource(
      "/profile-without-products/:profile_id"
    )
  })

  // this is exactly the same as ProfileWithoutProducts right now....
  .factory("ProfileAbout", function($resource){
    return $resource(
      "/profile/:id/about"
    )
  })

  // this is exactly the same as ProfileWithoutProducts right now....
  .factory("ProfilePinboard", function($resource){
    return $resource(
      "/profile/:id/pinboard"
    )
  })

  .factory("ProfileCountries", function($resource){
    return $resource(
      "/profile/:id/countries"
    )
  })

  .factory("SummaryCards", function($resource){
    return $resource(
      "/profile/:id/collection/:namespace/:tag/summary-cards"
    )
  })

  .factory("ProfileKeyProducts", function($resource){
    return $resource(
      "/profile/:id/key-products",
      {},
      {
        get: {
          isArray: true
        }
      },
      {
        save: {
          isArray: true
        }
      }
    )
  })
  .factory("ProfileKeyMetrics", function($resource){
    return $resource(
      "/profile/:id/key-metrics",
      {},
      {
        get: {
          isArray: true
        }
      },
      {
        save: {
          isArray: true
        }
      }
    )
  })



  .factory("ProfileAwards", function($resource){
    return $resource(
      "/profile/:id/awards",
      {},
      {
        get: {
          isArray: true
        }
      }
    )

  })



  .factory('UserProduct', function ($resource) {

    return $resource(
     "/profile/:id/product/:tiid",
     {
          cache: false      
     }
    )
  })


  .factory('UsersProducts', function ($resource) {

    return $resource(
      "/profile/:id/products",
      {
        // default params go here
      },
      {
        update:{
          method: "PUT"
        },
        patch: {
          method: "POST",
          headers: {'X-HTTP-METHOD-OVERRIDE': 'PATCH'}

        },
        delete: {
          method: "DELETE",
          headers: {'Content-Type': 'application/json'}
        },
        query:{
          method: "GET",
          isArray: true,
          cache: true,
          params: {hide: "metrics,awards,aliases", embedded: "@embedded"}
        },
        poll:{
          method: "GET",
          isArray: true,
          cache: false
        },
        refresh: {
          method: "POST"
        },
        after_refresh_cleanup: {
          method: "POST",
          params: {action: "after-refresh-cleanup"}
        }
      }
    )
  })
  .factory('UsersProduct', function ($resource) {

    return $resource(
      "/profile/:id/product/:tiid",
      {},  // defaults go here
      {
        update:{
          method: "PUT"
        }
      }
    )
  })

  .factory('UsersUpdateStatus', function ($resource) {
    return $resource(
      "/profile/:id/refresh_status",
      {}, // default params
      {}  // method definitions
    )
  })


  .factory('UsersLinkedAccounts', function($resource){

    return $resource(
      "/profile/:id/linked-accounts/:account",
      {},
      {
        update:{
          method: "POST",
          params: {action: "update"}
        }
      }

    )


  })

  .factory('UsersPassword', function ($resource) {

    return $resource(
      "/profile/:id/password",
      {} // defaults
    )
  })

  .factory("UsersProductsCache", function(UsersProducts){
      var cache = []
      return {
        query: function(){}
      }
    })


  .factory("UsersSubscription", function($resource){
    return $resource(
      "/profile/:id/subscription",
      {
        token: null,
        coupon: null,
        plan: "base-yearly"
      },
      {
        delete: {
          method: "DELETE",
          headers: {'Content-Type': 'application/json'}
        }
      }
    )
  })


